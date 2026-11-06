from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationNote


async def add_note(session: AsyncSession, note: ApplicationNote) -> None:
    session.add(note)
    await session.flush()


async def get_note(
    session: AsyncSession, application_id: UUID, note_id: UUID
) -> ApplicationNote | None:
    return await session.scalar(
        select(ApplicationNote).where(
            ApplicationNote.id == note_id,
            ApplicationNote.application_id == application_id,
        )
    )
