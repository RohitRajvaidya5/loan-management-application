from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import bearer_scheme, get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_claims,
    hash_password,
    token_digest,
    verify_password,
)
from app.database.session import get_db
from app.enums.audit import AuditAction
from app.models import RevokedToken, User
from app.schemas.auth import (
    AuthenticatedUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
)
from app.services.audit import record_audit_event
from app.services.auth import authenticate_user
from app.services.loan_application_service import application_transaction
from app.services.rate_limit import limit_login_attempts

router = APIRouter()


@router.post(
    "/token", response_model=TokenResponse, dependencies=[Depends(limit_login_attempts)]
)
async def issue_access_token(
    credentials: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user = await authenticate_user(session, credentials)
    if user is None:
        async with application_transaction(session):
            record_audit_event(
                session,
                request,
                None,
                action=AuditAction.LOGIN_FAILED,
                entity_type="authentication",
                entity_id=None,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with application_transaction(session):
        user.last_login_at = datetime.now(UTC)
        record_audit_event(
            session,
            request,
            user,
            action=AuditAction.LOGIN_SUCCESS,
            entity_type="user",
            entity_id=user.id,
        )
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        access_token = create_access_token(
            subject=str(user.id),
            secret_key=settings.JWT_SECRET_KEY.get_secret_value(),
            expires_in_minutes=expires_in,
            token_version=user.token_version,
        )
    return TokenResponse(access_token=access_token, expires_in=expires_in * 60)


@router.get("/me", response_model=AuthenticatedUserResponse)
async def read_authenticated_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    claims = decode_access_claims(
        credentials.credentials, settings.JWT_SECRET_KEY.get_secret_value()
    )
    async with application_transaction(session):
        await session.execute(
            insert(RevokedToken)
            .values(
                token_digest=token_digest(credentials.credentials),
                expires_at=datetime.fromtimestamp(claims["exp"], UTC),
            )
            .on_conflict_do_nothing()
        )
        record_audit_event(
            session,
            request,
            user,
            action=AuditAction.LOGOUT,
            entity_type="user",
            entity_id=user.id,
        )
    return Response(status_code=204)


@router.post("/password", status_code=204)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    initial_version = actor.token_version
    async with application_transaction(session):
        user = await session.get(
            User, actor.id, with_for_update={"of": User}, populate_existing=True
        )
        if user is None or not user.is_active or user.token_version != initial_version:
            raise HTTPException(
                status_code=401, detail="Could not validate credentials."
            )
        if not verify_password(
            payload.current_password.get_secret_value(), user.password_hash
        ):
            raise HTTPException(
                status_code=400, detail="Current password is incorrect."
            )
        if verify_password(payload.new_password.get_secret_value(), user.password_hash):
            raise HTTPException(
                status_code=422,
                detail="New password must differ from the current password.",
            )
        user.password_hash = hash_password(payload.new_password.get_secret_value())
        user.token_version += 1
        record_audit_event(
            session,
            request,
            user,
            action=AuditAction.PASSWORD_CHANGED,
            entity_type="user",
            entity_id=user.id,
        )
    return Response(status_code=204)
