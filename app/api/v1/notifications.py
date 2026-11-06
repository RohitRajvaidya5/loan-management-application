from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.models import Notification, User
from app.schemas.common import Page
from app.schemas.notifications import NotificationResponse
from app.services.audit import record_audit_event
from app.services.loan_application_service import application_transaction

router = APIRouter(
    dependencies=[
        Depends(require_role("administrator")),
        Depends(require_permission("notifications:read")),
    ]
)
Session = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=Page[NotificationResponse])
async def list_notifications(
    session: Session,
    status: Literal["PENDING", "PROCESSING", "SENT", "FAILED"] | None = None,
    event_type: Annotated[str | None, Query(max_length=60)] = None,
    application_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    conditions = []
    for column, value in (
        (Notification.status, status),
        (Notification.event_type, event_type),
        (Notification.application_id, application_id),
    ):
        if value is not None:
            conditions.append(column == value)
    total = (
        await session.scalar(
            select(func.count()).select_from(Notification).where(*conditions)
        )
        or 0
    )
    items = await session.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[NotificationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def notification_details(notification_id: UUID, session: Session):
    notification = await session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return notification


@router.post(
    "/{notification_id}/retry",
    response_model=NotificationResponse,
    dependencies=[Depends(require_permission("notifications:retry"))],
)
async def retry_notification(
    notification_id: UUID,
    session: Session,
    request: Request,
    actor: Annotated[User, Depends(require_role("administrator"))],
):
    async with application_transaction(session):
        notification = await session.get(
            Notification, notification_id, with_for_update=True, populate_existing=True
        )
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found.")
        if notification.status != "FAILED":
            raise HTTPException(
                status_code=409, detail="Only failed notifications can be retried."
            )
        notification.status = "PENDING"
        notification.retry_count = 0
        notification.available_at = datetime.now(UTC)
        notification.last_error = None
        record_audit_event(
            session,
            request,
            actor,
            action="notification.retried",
            entity_type="notification",
            entity_id=notification.id,
        )
        await session.flush()
        return NotificationResponse.model_validate(notification)
