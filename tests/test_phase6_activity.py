import json
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from starlette.requests import Request

from app.core.security import create_access_token, decode_access_claims, token_digest
from app.enums.audit import AuditAction
from app.models import User
from app.services.audit import DETAIL_SCHEMAS, record_audit_event


def test_audit_registry_covers_all_supported_actions():
    assert set(DETAIL_SCHEMAS) == set(AuditAction)


def test_audit_metadata_is_bounded_and_does_not_trust_forwarded_ip():
    session = Mock()
    request = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 1234),
            "headers": [
                (b"user-agent", b"test\r\nagent" + b"x" * 1000),
                (b"x-forwarded-for", b"192.0.2.99"),
                (b"authorization", b"Bearer never-store-this"),
            ],
        }
    )
    actor = User(id=uuid4())
    record_audit_event(
        session,
        request,
        actor,
        action=AuditAction.LOGIN_SUCCESS,
        entity_type="user",
        entity_id=actor.id,
    )
    audit = session.add.call_args.args[0]
    assert audit.user_id == actor.id
    assert audit.ip_address == "127.0.0.1"
    assert len(audit.user_agent) <= 512
    assert "\r" not in audit.user_agent and "\n" not in audit.user_agent
    assert audit.details is None
    assert "never-store-this" not in repr(audit.__dict__)


@pytest.mark.parametrize("action", list(AuditAction))
@pytest.mark.parametrize(
    "key", ["password", "access_token", "note", "email", "bank_account", "filename"]
)
def test_audit_details_reject_unapproved_sensitive_fields(action, key):
    session = Mock()
    entity, _ = DETAIL_SCHEMAS[action]
    with pytest.raises(ValueError) as error:
        record_audit_event(
            session,
            Request({"type": "http"}),
            None,
            action=action,
            entity_type=entity,
            entity_id=None,
            details={key: "sensitive-value"},
        )
    assert "sensitive-value" not in str(error.value)
    session.add.assert_not_called()


def test_audit_rejects_unknown_action_entity_and_field_values():
    request = Request({"type": "http"})
    session = Mock()
    with pytest.raises(ValueError):
        record_audit_event(
            session, request, None, action="unknown", entity_type="user", entity_id=None
        )
    with pytest.raises(ValueError):
        record_audit_event(
            session,
            request,
            None,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            entity_id=None,
        )
    with pytest.raises(ValueError):
        record_audit_event(
            session,
            request,
            None,
            action=AuditAction.USER_UPDATED,
            entity_type="user",
            entity_id=None,
            details={"fields": ["secret-value"]},
        )
    session.add.assert_not_called()


def test_audit_safe_details_are_serializable():
    session = Mock()
    identifier = uuid4()
    record_audit_event(
        session,
        Request({"type": "http", "client": ("not-an-ip", 1)}),
        None,
        action=AuditAction.NOTE_CREATED,
        entity_type="application_note",
        entity_id=uuid4(),
        details={"application_id": identifier},
    )
    event = session.add.call_args.args[0]
    assert event.user_id is None and event.ip_address is None
    assert json.loads(json.dumps(event.details)) == {"application_id": str(identifier)}


def test_new_tokens_are_unique_and_versioned_and_digests_are_one_way():
    secret = "phase6-test-signing-secret-at-least-32-chars"
    first = create_access_token("user", secret, token_version=3)
    second = create_access_token("user", secret, token_version=3)
    assert first != second
    assert decode_access_claims(first, secret)["ver"] == 3
    assert len(token_digest(first)) == 64 and first not in token_digest(first)
    claims = decode_access_claims(first, secret)
    for bad_version in (-1, True, "3", None):
        modified = jwt.encode({**claims, "ver": bad_version}, secret, algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_claims(modified, secret)
    legacy = {key: value for key, value in claims.items() if key not in ("ver", "jti")}
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_claims(jwt.encode(legacy, secret, algorithm="HS256"), secret)
