from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_claims, token_digest
from app.database.session import get_db
from app.models import Permission, RevokedToken, Role, User, role_permissions

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        claims = decode_access_claims(
            credentials.credentials,
            settings.JWT_SECRET_KEY.get_secret_value(),
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthorized
    if user.token_version != claims["ver"]:
        raise unauthorized
    if (
        await session.get(RevokedToken, token_digest(credentials.credentials))
        is not None
    ):
        raise unauthorized

    return user


def require_permission(permission_name: str) -> Callable[..., Awaitable[User]]:
    if not permission_name or not permission_name.strip():
        raise ValueError("Permission name must not be blank.")
    permission_name = permission_name.strip()

    async def permission_dependency(
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        result = await session.execute(
            select(Permission.id)
            .join(
                role_permissions,
                role_permissions.c.permission_id == Permission.id,
            )
            .where(
                role_permissions.c.role_id == user.role_id,
                Permission.name == permission_name,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return user

    return permission_dependency


def require_role(*role_names: str) -> Callable[..., Awaitable[User]]:
    if not role_names or any(not name or not name.strip() for name in role_names):
        raise ValueError("At least one non-blank role name is required.")
    role_names = tuple(name.strip() for name in role_names)

    async def role_dependency(
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        result = await session.execute(
            select(Role.id).where(
                Role.id == user.role_id,
                Role.name.in_(role_names),
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )

        return user

    return role_dependency
