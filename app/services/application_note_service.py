from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.audit import AuditAction
from app.models import ApplicationNote, User
from app.repositories.application_note_repository import add_note
from app.repositories.document_repository import get_application
from app.schemas.applications import ApplicationNoteCreate, ApplicationNoteResponse
from app.services.audit import record_audit_event
from app.services.loan_application_service import application_transaction


async def create_note(
    session: AsyncSession,
    application_id: UUID,
    payload: ApplicationNoteCreate,
    actor: User,
    request: Request,
) -> ApplicationNoteResponse:
    async with application_transaction(session):
        await get_application(session, application_id)
        note = ApplicationNote(
            application_id=application_id, author_id=actor.id, note=payload.note
        )
        await add_note(session, note)
        record_audit_event(
            session,
            request,
            actor,
            action=AuditAction.NOTE_CREATED,
            entity_type="application_note",
            entity_id=note.id,
            details={"application_id": str(application_id)},
        )
        return ApplicationNoteResponse.model_validate(note)
