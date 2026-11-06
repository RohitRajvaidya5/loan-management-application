from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_permission, require_role
from app.database.session import get_db
from app.models import User


def create_rbac_client(
    result_value: object | None,
    role_id=None,
) -> TestClient:
    user = SimpleNamespace(role_id=role_id or uuid4())
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=result_value)
    )

    async def override_current_user() -> User:
        return user

    async def override_get_db():
        yield session

    router = APIRouter()

    @router.get(
        "/permission",
        dependencies=[Depends(require_permission("customers:read"))],
    )
    async def permission_protected_route():
        return {"authorized": True}

    @router.get(
        "/role",
        dependencies=[Depends(require_role("administrator"))],
    )
    async def role_protected_route():
        return {"authorized": True}

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides = {
        get_db: override_get_db,
    }

    app.dependency_overrides[get_current_user] = override_current_user
    return TestClient(app)


def test_permission_dependency_allows_granted_permission() -> None:
    with create_rbac_client(uuid4()) as client:
        response = client.get("/permission")

    assert response.status_code == 200
    assert response.json() == {"authorized": True}


def test_permission_dependency_rejects_missing_permission() -> None:
    with create_rbac_client(None) as client:
        response = client.get("/permission")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions."


def test_role_dependency_allows_allowed_role() -> None:
    with create_rbac_client(uuid4()) as client:
        response = client.get("/role")

    assert response.status_code == 200
    assert response.json() == {"authorized": True}


def test_role_dependency_rejects_other_roles() -> None:
    with create_rbac_client(None) as client:
        response = client.get("/role")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role."


def test_authorization_dependencies_reject_blank_requirements() -> None:
    with pytest.raises(ValueError):
        require_permission(" ")

    with pytest.raises(ValueError):
        require_role()

    with pytest.raises(ValueError):
        require_role("administrator", "")
