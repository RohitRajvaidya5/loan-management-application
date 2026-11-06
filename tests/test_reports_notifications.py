import asyncio
import csv
import io
import os
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError

from app.api.v1.reports import csv_response, safe_cell
from app.core.config import Settings, settings
from app.core.http import configure_http
from app.main import app
from app.models import LoanApplication
from app.repositories.report_repository import check_group_limit
from app.services.email_service import SMTPEmailSender
from app.services.notification_service import enqueue_application_email
from app.templates.emails import MESSAGES, render_email


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(A1)", "-2+3", "@command", "  =1", "\t=1", "\r=1", "\n=1"]
)
def test_csv_formula_safety(value):
    assert safe_cell(value) == "'" + value


def test_csv_shape_quoting_and_limit():
    response = csv_response(
        ["name", "amount"], [["a,b\nc", "100.25"], [None, 0]], "safe"
    )
    assert list(csv.reader(io.StringIO(response.body.decode()))) == [
        ["name", "amount"],
        ["a,b\nc", "100.25"],
        ["", "0"],
    ]
    assert "attachment" in response.headers["content-disposition"]
    with pytest.raises(HTTPException) as error:
        csv_response(["id"], [[1]] * 5001, "too-big")
    assert error.value.status_code == 422
    check_group_limit(5000)
    with pytest.raises(HTTPException) as error:
        check_group_limit(5001)
    assert error.value.status_code == 422


@pytest.mark.parametrize("event", list(MESSAGES))
def test_generic_email_templates(event):
    subject, text, html = render_email(event)
    assert subject and text and "<html>" in html
    for sensitive in ("500000", "salary", "PAN", "Aadhaar", "password", "token"):
        assert sensitive not in text
    with pytest.raises(ValueError):
        render_email("unknown-template")


def test_smtp_transport_tls_auth_and_stable_identifier(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender")
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("never-log-this"))
    smtp_factory = MagicMock()
    smtp = smtp_factory.return_value.__enter__.return_value
    smtp.send_message.return_value = {}
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", smtp_factory)
    identifier = uuid4()
    reference = SMTPEmailSender().send(
        identifier, "recipient@example.com", "application_submitted"
    )
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sender", "never-log-this")
    message = smtp.send_message.call_args.args[0]
    assert message.is_multipart() and str(identifier) in reference
    assert message["Message-ID"] == reference
    assert message["To"] == "recipient@example.com"


def test_smtp_disabled_never_connects(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    with pytest.raises(RuntimeError, match="disabled"):
        SMTPEmailSender().send(
            uuid4(), "recipient@example.com", "application_submitted"
        )


@pytest.mark.parametrize("recipient", [None, "not-an-email-address"])
def test_missing_invalid_recipient_is_logged_without_queuing(
    monkeypatch, caplog, recipient
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    caplog.set_level("INFO", logger="app.services.notification_service")
    session = AsyncMock()
    session.scalar.return_value = recipient
    application = LoanApplication(id=uuid4(), customer_id=uuid4(), version=1)
    asyncio.run(enqueue_application_email(session, application, "status_updated"))
    session.execute.assert_not_awaited()
    assert "notification.skipped_" in caplog.text
    if recipient:
        assert recipient not in caplog.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"CORS_ORIGINS": ["*"]},
        {"CORS_ORIGINS": ["https://site.test/path"]},
        {"CORS_ORIGINS": ["https://user:password@site.test"]},
        {"EMAIL_SENDER_NAME": "sender\r\nBcc: other@example.com"},
        {"SMTP_USERNAME": "without-password"},
        {"NOTIFICATION_LEASE_SECONDS": 30, "SMTP_TIMEOUT_SECONDS": 30},
        {"APP_ENV": "production", "DEBUG": True},
        {"APP_ENV": "production", "CORS_ORIGINS": ["http://localhost:3000"]},
        {"APP_ENV": "production", "AUTH_RATE_LIMIT_ENABLED": False},
        {
            "APP_ENV": "production",
            "NOTIFICATIONS_ENABLED": True,
            "SMTP_STARTTLS": False,
        },
    ],
)
def test_unsafe_configuration_rejected(overrides):
    values = {
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "JWT_SECRET_KEY": "safe-randomized-test-secret-0123456789",
        "AUTH_RATE_LIMIT_ENABLED": True,
    } | overrides
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_errors_redact_validation_inputs_and_database_details(caplog):
    api = FastAPI()
    configure_http(api)

    class Payload(BaseModel):
        password: int

    @api.post("/validate")
    def validate(payload: Payload):
        return payload

    @api.get("/database")
    def database():
        raise OperationalError(
            "SELECT secret", {"password": "do-not-leak"}, Exception("db-password")
        )

    @api.get("/crash")
    def crash():
        raise RuntimeError("private-provider-password")

    with TestClient(api, raise_server_exceptions=False) as client:
        invalid = client.post("/validate", json={"password": "do-not-leak"})
        assert (
            invalid.status_code == 422 and invalid.json()["code"] == "VALIDATION_ERROR"
        )
        assert "input" not in invalid.json()["detail"][0]
        assert "do-not-leak" not in invalid.text
        failure = client.get("/database")
        assert failure.status_code == 503
        crash = client.get("/crash")
        assert crash.status_code == 500 and crash.json()["code"] == "INTERNAL_ERROR"
        for response in (invalid, failure, crash):
            assert UUID(response.json()["request_id"])
            assert response.headers["x-request-id"] == response.json()["request_id"]
        assert all(
            secret not in caplog.text
            for secret in ("do-not-leak", "db-password", "private-provider-password")
        )


def test_correlation_id_and_openapi_report_filters():
    with TestClient(app) as client:
        request_id = str(uuid4())
        response = client.get("/health/live", headers={"X-Request-ID": request_id})
        assert response.headers["x-request-id"] == request_id
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        assert UUID(
            client.get("/health/live", headers={"X-Request-ID": "not-a-uuid"}).headers[
                "x-request-id"
            ]
        )
    schema = app.openapi()
    parameters = schema["paths"]["/api/v1/reports/loan-types"]["get"]["parameters"]
    assert {item["name"] for item in parameters} >= {
        "date_from",
        "date_to",
        "loan_type_id",
        "page",
        "page_size",
    }
    assert "requestBody" not in schema["paths"]["/api/v1/reports/loan-types"]["get"]
    assert schema["paths"]["/api/v1/reports/financial-summary"]["get"]["security"]
    assert schema["paths"]["/api/v1/reports/loan-types"]["get"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")


def test_production_docs_disabled_and_cors_explicit():
    environment = dict(os.environ) | {
        "APP_ENV": "production",
        "DEBUG": "false",
        "AUTH_RATE_LIMIT_ENABLED": "true",
        "NOTIFICATIONS_ENABLED": "false",
        "CORS_ORIGINS": '["https://frontend.example.com"]',
        "JWT_SECRET_KEY": "independent-ci-config-check-0123456789-abcdefgh",
    }
    script = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    for path in ('/docs', '/redoc', '/openapi.json'):
        assert client.get(path).status_code == 404
    response = client.get('/health/live', headers={'Origin': 'https://frontend.example.com'})
    assert response.headers['access-control-allow-origin'] == 'https://frontend.example.com'
    assert 'access-control-allow-origin' not in client.get('/health/live', headers={'Origin': 'https://attacker.example.com'}).headers
    assert client.options('/api/v1/loan-applications', headers={'Origin': 'https://frontend.example.com', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type'}).status_code == 200
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
