from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.core.security import hash_password
from app.database.session import get_db
from app.enums.audit import AuditAction
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.users import (
    UserActiveUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()


async def _get_user(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


async def _require_role_exists(session: AsyncSession, role_id: UUID) -> None:
    if await session.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found.")


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("users:create"))],
)
async def create_user(
    payload: UserCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_role("administrator"))],
) -> User:
    await _require_role_exists(session, payload.role_id)
    user = User(
        full_name=payload.full_name,
        email=str(payload.email),
        password_hash=hash_password(payload.password.get_secret_value()),
        role_id=payload.role_id,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from None

    record_audit_event(
        session,
        request,
        actor,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        details={"role_id": str(user.role_id)},
    )
    await session.commit()
    await session.refresh(user)
    return user


@router.get(
    "",
    response_model=Page[UserResponse],
    dependencies=[
        Depends(require_role("administrator")),
        Depends(require_permission("users:read")),
    ],
)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
) -> Page[UserResponse]:
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=422,
            detail="Page must be positive and page_size must be between 1 and 100.",
        )
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    result = await session.scalars(
        select(User)
        .order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=list(result.all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[
        Depends(require_role("administrator")),
        Depends(require_permission("users:read")),
    ],
)
async def get_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await _get_user(session, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("users:update"))],
)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_role("administrator"))],
) -> User:
    user = await session.get(
        User, user_id, with_for_update={"of": User}, populate_existing=True
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    previous_role_id = user.role_id
    updates = payload.model_dump(exclude_unset=True)
    if "role_id" in updates:
        await _require_role_exists(session, updates["role_id"])
    if "email" in updates:
        updates["email"] = str(updates["email"])
    for field, value in updates.items():
        setattr(user, field, value)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from None

    record_audit_event(
        session,
        request,
        actor,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        details={"fields": sorted(updates)},
    )
    if user.role_id != previous_role_id:
        user.token_version += 1
        record_audit_event(
            session,
            request,
            actor,
            action=AuditAction.USER_ROLE_CHANGED,
            entity_type="user",
            entity_id=user.id,
            details={
                "previous_role_id": str(previous_role_id),
                "role_id": str(user.role_id),
            },
        )
    await session.commit()
    await session.refresh(user)
    return user


@router.patch(
    "/{user_id}/activation",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("users:deactivate"))],
)
async def set_user_activation(
    user_id: UUID,
    payload: UserActiveUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_role("administrator"))],
) -> User:
    user = await session.get(
        User, user_id, with_for_update={"of": User}, populate_existing=True
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.is_active == payload.is_active:
        return user
    user.is_active = payload.is_active
    user.token_version += 1
    record_audit_event(
        session,
        request,
        actor,
        action="user.activated" if user.is_active else "user.deactivated",
        entity_type="user",
        entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return user
