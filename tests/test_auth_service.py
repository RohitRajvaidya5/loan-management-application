import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.schemas.auth import LoginRequest
from app.services.auth import authenticate_user


def session_returning(user: object | None) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=user)
    )
    return session


def test_authenticate_user_returns_active_user_with_valid_password() -> None:
    user = SimpleNamespace(
        email="customer@example.com",
        password_hash=hash_password("correct password"),
        is_active=True,
    )
    session = session_returning(user)

    result = asyncio.run(
        authenticate_user(
            session,
            LoginRequest(email=user.email, password="correct password"),
        )
    )

    assert result is user


def test_authenticate_user_rejects_incorrect_password() -> None:
    user = SimpleNamespace(
        email="customer@example.com",
        password_hash=hash_password("correct password"),
        is_active=True,
    )
    session = session_returning(user)

    result = asyncio.run(
        authenticate_user(
            session,
            LoginRequest(email=user.email, password="incorrect password"),
        )
    )

    assert result is None


def test_authenticate_user_rejects_inactive_user() -> None:
    user = SimpleNamespace(
        email="customer@example.com",
        password_hash=hash_password("correct password"),
        is_active=False,
    )
    session = session_returning(user)

    result = asyncio.run(
        authenticate_user(
            session,
            LoginRequest(email=user.email, password="correct password"),
        )
    )

    assert result is None


def test_authenticate_user_rejects_unknown_email() -> None:
    session = session_returning(None)

    result = asyncio.run(
        authenticate_user(
            session,
            LoginRequest(email="unknown@example.com", password="any password"),
        )
    )

    assert result is None


def test_login_request_strips_email_and_hides_password() -> None:
    credentials = LoginRequest(
        email="  customer@example.com  ",
        password="customer secret",
    )

    assert credentials.email == "customer@example.com"
    assert credentials.password.get_secret_value() == "customer secret"
    assert "customer secret" not in repr(credentials)


def test_login_request_rejects_blank_email() -> None:
    with pytest.raises(ValueError):
        LoginRequest(email="   ", password="customer secret")
