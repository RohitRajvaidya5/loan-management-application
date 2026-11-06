from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, LoanApplication


async def get_application(
    session: AsyncSession, application_id: UUID
) -> LoanApplication:
    application = await session.get(LoanApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found.")
    return application


async def get_document(
    session: AsyncSession, document_id: UUID, *, lock: bool = False
) -> Document:
    statement = select(Document).where(Document.id == document_id)
    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )
    document = await session.scalar(statement)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


def check_editable(document: Document, expected_version: int) -> None:
    if document.version != expected_version:
        raise HTTPException(
            status_code=409, detail="Document has changed. Reload it and retry."
        )
    if document.deleted_at is not None or document.replaced_at is not None:
        raise HTTPException(
            status_code=409, detail="Deleted or replaced documents cannot be modified."
        )
