from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password
from app.database.session import get_db
from app.main import app

TEST_SECRET = "test-signing-key-with-at-least-32-characters"


def test_access_token_round_trips_subject() -> None:
    token = create_access_token("user-123", TEST_SECRET)

    assert decode_access_token(token, TEST_SECRET) == "user-123"


def test_access_token_rejects_wrong_signing_key() -> None:
    token = create_access_token("user-123", TEST_SECRET)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, "a-different-signing-key-with-32-chars")


def test_access_token_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-123",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "type": "access",
            "ver": 0,
            "jti": uuid4().hex,
        },
        TEST_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, TEST_SECRET)


def test_access_token_rejects_non_access_token() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-123",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "type": "refresh",
        },
        TEST_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, TEST_SECRET)


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch):
    user = SimpleNamespace(
        id=uuid4(),
        full_name="Test Customer",
        email="customer@example.com",
        is_active=True,
        password_hash=hash_password("test password"),
        token_version=0,
    )
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = None
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=user)
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        type(settings.JWT_SECRET_KEY)(TEST_SECRET),
    )
    try:
        with TestClient(app) as client:
            yield client, user
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_auth_endpoints_issue_token_and_return_current_user(auth_client) -> None:
    client, user = auth_client
    response = client.post(
        "/api/v1/auth/token",
        json={"email": user.email, "password": "test password"},
    )

    assert response.status_code == 200
    token_data = response.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    current_user_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert current_user_response.status_code == 200
    assert current_user_response.json() == {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "is_active": True,
    }


def test_current_user_endpoint_requires_bearer_token(auth_client) -> None:
    client, _ = auth_client

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_token_endpoint_rejects_invalid_password(auth_client) -> None:
    client, user = auth_client

    response = client.post(
        "/api/v1/auth/token",
        json={"email": user.email, "password": "wrong password"},
    )

    assert response.status_code == 401


def test_current_user_endpoint_rejects_malformed_token(auth_client) -> None:
    client, _ = auth_client

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


def test_current_user_endpoint_rejects_non_uuid_subject(auth_client) -> None:
    client, _ = auth_client
    token = create_access_token(
        "not-a-uuid",
        settings.JWT_SECRET_KEY.get_secret_value(),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_current_user_endpoint_rejects_deactivated_user(auth_client) -> None:
    client, user = auth_client
    user.is_active = False
    token = create_access_token(
        str(user.id),
        settings.JWT_SECRET_KEY.get_secret_value(),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
