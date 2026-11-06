from typing import Literal
from uuid import UUID

from sqlalchemy import (
    String,
    Text,
    Uuid,
    and_,
    cast,
    func,
    literal,
    null,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.audit import AuditAction
from app.models import (
    ApplicationNote,
    ApplicationStatusHistory,
    AuditLog,
    Document,
    User,
)
from app.schemas.activity import ApplicationActivity
from app.schemas.common import Page


async def application_activity(
    session: AsyncSession,
    application_id: UUID,
    page: int,
    page_size: int,
    sort: Literal["asc", "desc"],
) -> Page[ApplicationActivity]:
    notes = select(
        ApplicationNote.id.label("id"),
        literal("note").label("source"),
        literal(AuditAction.NOTE_CREATED.value).label("action"),
        ApplicationNote.created_at.label("occurred_at"),
        ApplicationNote.author_id.label("actor_id"),
        ApplicationNote.note.label("note"),
        cast(null(), Text).label("remarks"),
        cast(null(), String).label("old_status"),
        cast(null(), String).label("new_status"),
        cast(null(), Uuid).label("document_id"),
    ).where(ApplicationNote.application_id == application_id)
    statuses = select(
        ApplicationStatusHistory.id,
        literal("status_history"),
        literal(AuditAction.APPLICATION_STATUS_CHANGED.value),
        ApplicationStatusHistory.created_at,
        ApplicationStatusHistory.changed_by,
        cast(null(), Text),
        ApplicationStatusHistory.remarks,
        cast(ApplicationStatusHistory.old_status, String),
        cast(ApplicationStatusHistory.new_status, String),
        cast(null(), Uuid),
    ).where(ApplicationStatusHistory.application_id == application_id)
    audit = (
        select(
            AuditLog.id,
            literal("audit"),
            AuditLog.action,
            AuditLog.created_at,
            AuditLog.user_id,
            cast(null(), Text),
            cast(null(), Text),
            cast(null(), String),
            cast(null(), String),
            Document.id,
        )
        .outerjoin(
            Document,
            and_(AuditLog.entity_type == "document", AuditLog.entity_id == Document.id),
        )
        .where(
            or_(
                and_(
                    AuditLog.entity_type == "loan_application",
                    AuditLog.entity_id == application_id,
                ),
                Document.application_id == application_id,
            ),
            AuditLog.action.not_in(
                (AuditAction.NOTE_CREATED, AuditAction.APPLICATION_STATUS_CHANGED)
            ),
        )
    )
    events = union_all(notes, statuses, audit).subquery()
    total = await session.scalar(select(func.count()).select_from(events)) or 0
    order = (
        (events.c.occurred_at.asc(), events.c.source.asc(), events.c.id.asc())
        if sort == "asc"
        else (events.c.occurred_at.desc(), events.c.source.desc(), events.c.id.desc())
    )
    result = await session.execute(
        select(events, User.full_name.label("actor_name"))
        .outerjoin(User, User.id == events.c.actor_id)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[
            ApplicationActivity.model_validate(dict(row)) for row in result.mappings()
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
