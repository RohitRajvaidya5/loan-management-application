import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.v1.dependencies import get_current_user
from app.database.session import get_db
from app.enums.application_status import ApplicationStatus
from app.main import app
from app.models import (
    ApplicationStatusHistory,
    AuditLog,
    Customer,
    LoanApplication,
    LoanType,
    User,
)
from app.schemas.applications import LoanApplicationCreate
from app.services.loan_application_service import submit_application


@pytest.fixture
def submission_context() -> Iterator[tuple[TestClient, AsyncMock, list, dict]]:
    actor = User(id=uuid4(), role_id=uuid4(), is_active=True)
    customer = Customer(id=uuid4(), full_name="Test Customer", phone="1234567890")
    loan_type = LoanType(id=uuid4(), name="Personal Loan", is_active=True)
    session = AsyncMock(spec=AsyncSession)
    added = []
    session.add.side_effect = added.append

    async def get_record(model, record_id):
        if model is Customer:
            return customer if record_id == customer.id else None
        if model is LoanType:
            return loan_type if record_id == loan_type.id else None
        return None

    async def flush():
        for item in added:
            if isinstance(item, LoanApplication):
                item.id = item.id or uuid4()
                item.version = item.version or 1
                item.created_at = item.updated_at = datetime.now(UTC)
                item.customer = customer
                item.loan_type = loan_type
                item.assigned_user = None

    async def execute(statement):
        # Authorization selects roles/permissions; the repository selects the application.
        application_query = (
            statement.column_descriptions[0].get("entity") is LoanApplication
        )
        value = (
            next((item for item in added if isinstance(item, LoanApplication)), None)
            if application_query
            else uuid4()
        )
        result = Mock()
        result.scalar_one.return_value = 1
        result.unique.return_value = result
        result.scalar_one_or_none.return_value = value
        return result

    session.get.side_effect = get_record
    session.flush.side_effect = flush
    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor
    payload = {
        "customer_id": str(customer.id),
        "loan_type_id": str(loan_type.id),
        "requested_amount": "500000.00",
        "tenure_months": 60,
        "employment_type": "SALARIED",
        "monthly_income": "60000.00",
        "purpose": "Home renovation",
    }
    try:
        with TestClient(app) as client:
            yield client, session, added, payload
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("path", ["/api/v1/loan-applications", "/api/v1/applications"])
def test_submission_returns_created_application_and_records_events(
    submission_context, path
):
    client, session, added, payload = submission_context
    response = client.post(path, json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "NEW"
    assert body["requested_amount"] == "500000.00"
    assert body["customer"]["full_name"] == "Test Customer"
    assert body["loan_type"]["name"] == "Personal Loan"
    assert body["assigned_to"] is None
    assert body["assigned_user"] is None
    assert body["application_number"].startswith("LN-")
    assert body["application_number"].endswith("-000001")
    assert body["version"] == 1
    history = next(item for item in added if isinstance(item, ApplicationStatusHistory))
    audit = next(item for item in added if isinstance(item, AuditLog))
    assert history.application_id == audit.entity_id
    assert history.old_status is None
    assert history.new_status is ApplicationStatus.NEW
    assert history.changed_by == audit.user_id
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.parametrize("missing", ["customer_id", "loan_type_id"])
def test_submission_rejects_missing_references(submission_context, missing):
    client, session, added, payload = submission_context
    payload[missing] = str(uuid4())
    response = client.post("/api/v1/loan-applications", json=payload)

    assert response.status_code == 404
    assert not added
    session.commit.assert_not_awaited()


def test_submission_rejects_inactive_loan_type(submission_context):
    client, session, added, payload = submission_context
    original_get = session.get.side_effect

    async def get_record(model, record_id):
        record = await original_get(model, record_id)
        if model is LoanType and record is not None:
            record.is_active = False
        return record

    session.get.side_effect = get_record
    response = client.post("/api/v1/loan-applications", json=payload)
    assert response.status_code == 404
    assert not added
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requested_amount", 0),
        ("requested_amount", -1),
        ("tenure_months", 0),
        ("tenure_months", 601),
        ("monthly_income", 0),
        ("monthly_income", -1),
        ("monthly_income", "NaN"),
        ("requested_amount", "Infinity"),
        ("requested_amount", "10000000000000.00"),
        ("requested_amount", "1.001"),
        ("employment_type", "INVALID"),
        ("customer_id", "invalid-uuid"),
    ],
)
def test_submission_rejects_invalid_input(submission_context, field, value):
    client, session, added, payload = submission_context
    payload[field] = value
    response = client.post("/api/v1/loan-applications", json=payload)
    assert response.status_code == 422
    assert not added
    session.commit.assert_not_awaited()


def test_submission_requires_authorization(submission_context):
    client, session, added, payload = submission_context
    session.execute.side_effect = None
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    response = client.post("/api/v1/loan-applications", json=payload)
    assert response.status_code == 403
    assert not added


def test_submission_requires_authentication(submission_context):
    client, session, added, payload = submission_context
    app.dependency_overrides.pop(get_current_user)
    response = client.post("/api/v1/loan-applications", json=payload)
    assert response.status_code == 401
    assert not added
    session.commit.assert_not_awaited()


def test_submission_rolls_back_when_commit_fails(submission_context):
    _, session, _, payload = submission_context
    session.commit.side_effect = SQLAlchemyError("Database commit failed.")
    actor = User(id=uuid4())
    request = Request({"type": "http", "client": ("127.0.0.1", 12345)})

    with pytest.raises(SQLAlchemyError, match="Database commit failed"):
        asyncio.run(
            submit_application(
                session, LoanApplicationCreate(**payload), actor, request
            )
        )
    session.rollback.assert_awaited_once()


@pytest.mark.parametrize("base", ["/api/v1/applications", "/api/v1/loan-applications"])
@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        ("GET", "", None),
        ("GET", "/00000000-0000-0000-0000-000000000001", None),
        (
            "PATCH",
            "/00000000-0000-0000-0000-000000000001",
            {"purpose": "Edit", "expected_version": 1},
        ),
        (
            "PATCH",
            "/00000000-0000-0000-0000-000000000001/status",
            {"status": "CONTACTED", "expected_version": 1},
        ),
        (
            "PATCH",
            "/00000000-0000-0000-0000-000000000001/assignment",
            {"assigned_to": None, "expected_version": 1},
        ),
        (
            "POST",
            "/emi",
            {"principal": "1000", "annual_interest_rate": "10", "tenure_months": 12},
        ),
    ],
)
def test_engine_routes_deny_unprivileged_users(
    submission_context, base, method, suffix, payload
):
    client, session, added, _ = submission_context
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.side_effect = None
    session.execute.return_value = result
    response = client.request(method, base + suffix, json=payload)
    assert response.status_code == 403
    assert not added
    session.commit.assert_not_awaited()
