from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.schemas.audit import AuditLogResponse
from app.schemas.common import Page


async def search_audit_logs(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    entity_type: str | None,
    entity_id: UUID | None,
    action: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
    sort: Literal["asc", "desc"],
) -> Page[AuditLogResponse]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must not be after date_to."
        )
    filters = []
    for column, value in (
        (AuditLog.user_id, user_id),
        (AuditLog.entity_type, entity_type),
        (AuditLog.entity_id, entity_id),
        (AuditLog.action, action),
    ):
        if value is not None:
            filters.append(column == value)
    if date_from is not None:
        filters.append(
            AuditLog.created_at >= datetime.combine(date_from, time.min, UTC)
        )
    if date_to is not None:
        if date_to == date.max:
            filters.append(
                AuditLog.created_at <= datetime.combine(date_to, time.max, UTC)
            )
        else:
            filters.append(
                AuditLog.created_at
                < datetime.combine(date_to + timedelta(days=1), time.min, UTC)
            )
    total = (
        await session.scalar(select(func.count()).select_from(AuditLog).where(*filters))
        or 0
    )
    order = (
        (AuditLog.created_at.asc(), AuditLog.id.asc())
        if sort == "asc"
        else (AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    records = await session.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[AuditLogResponse.model_validate(item) for item in records],
        total=total,
        page=page,
        page_size=page_size,
    )
