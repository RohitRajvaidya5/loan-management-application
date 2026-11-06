from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.enums.audit import AuditAction
from app.repositories.audit_log_repository import search_audit_logs
from app.schemas.audit import AuditLogResponse
from app.schemas.common import Page

router = APIRouter()
access = [
    Depends(require_role("administrator")),
    Depends(require_permission("audit_logs:read")),
]


@router.get("/actions", dependencies=access)
def supported_audit_actions() -> list[str]:
    return list(AuditAction)


@router.get("", response_model=Page[AuditLogResponse], dependencies=access)
async def list_audit_logs(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: UUID | None = None,
    entity_type: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    entity_id: UUID | None = None,
    action: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    sort: Literal["asc", "desc"] = "desc",
) -> Page[AuditLogResponse]:
    return await search_audit_logs(
        session,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort=sort,
    )
