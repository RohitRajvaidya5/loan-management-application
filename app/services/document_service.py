import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.enums.document import DocumentStatus, DocumentType
from app.models import Document, DocumentReview, User
from app.repositories.document_repository import (
    check_editable,
    get_application,
    get_document,
)
from app.schemas.documents import (
    DocumentDeletion,
    DocumentResponse,
    DocumentVerification,
)
from app.services.audit import record_audit_event
from app.services.file_validation import validate_upload
from app.services.loan_application_service import application_transaction
from app.services.notification_service import enqueue_application_email
from app.services.storage_service import DocumentStorage


async def upload_document(
    session: AsyncSession,
    application_id: uuid.UUID,
    document_type: DocumentType,
    upload: UploadFile,
    actor: User,
    request: Request,
    storage: DocumentStorage,
    *,
    replaces_id: uuid.UUID | None = None,
    expected_version: int | None = None,
) -> DocumentResponse:
    filename, mime, extension, content = await validate_upload(upload)
    key: str | None = None
    committed = False
    try:
        async with application_transaction(session):
            application = await get_application(session, application_id)
            previous = None
            if replaces_id is not None:
                previous = await get_document(session, replaces_id, lock=True)
                if expected_version is None:
                    raise ValueError("A replacement requires an expected version.")
                check_editable(previous, expected_version)
                if previous.application_id != application_id:
                    raise HTTPException(status_code=404, detail="Document not found.")
                if (
                    previous.document_type in DocumentType
                    and previous.document_type != document_type
                ):
                    raise HTTPException(
                        status_code=422,
                        detail="Replacement must retain the document category.",
                    )
            key = await storage.save(str(application_id), extension, content)
            document_id = uuid.uuid4()
            document = Document(
                id=document_id,
                application_id=application_id,
                uploaded_by=actor.id,
                document_type=document_type.value,
                original_filename=filename,
                storage_key=key,
                mime_type=mime,
                file_size=len(content),
                status=DocumentStatus.PENDING,
                version=1,
                document_group_id=previous.document_group_id
                if previous
                else document_id,
                revision=previous.revision + 1 if previous else 1,
                replaces_document_id=previous.id if previous else None,
            )
            if previous is not None:
                previous.replaced_at = datetime.now(UTC)
                previous.version += 1
            session.add(document)
            await session.flush()
            record_audit_event(
                session,
                request,
                actor,
                action="document.replaced" if previous else "document.uploaded",
                entity_type="document",
                entity_id=document.id,
                details={
                    "application_id": str(application_id),
                    "document_type": document.document_type,
                    "file_size": len(content),
                    "replaces_document_id": str(previous.id) if previous else None,
                },
            )
            await session.flush()
            response = DocumentResponse.model_validate(document)
            await enqueue_application_email(
                session,
                application,
                "document_uploaded",
                event_id=document.id,
                audience="staff",
            )
        committed = True
        return response
    finally:
        if key is not None and not committed:
            await storage.delete(key)


async def verify_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    payload: DocumentVerification,
    actor: User,
    request: Request,
) -> DocumentResponse:
    async with application_transaction(session):
        document = await get_document(session, document_id, lock=True)
        check_editable(document, payload.expected_version)
        if document.status == payload.status:
            raise HTTPException(
                status_code=409, detail="Document already has this review status."
            )
        previous_status = document.status
        document.status = payload.status
        document.version += 1
        document.verified_by = actor.id
        document.verified_at = datetime.now(UTC)
        document.review_remarks = payload.remarks
        review = DocumentReview(
            document_id=document.id,
            reviewed_by=actor.id,
            previous_status=previous_status,
            status=payload.status,
            remarks=payload.remarks,
            document_version=document.version,
        )
        session.add(review)
        record_audit_event(
            session,
            request,
            actor,
            action="document.reviewed",
            entity_type="document",
            entity_id=document.id,
            details={"previous_status": previous_status, "status": payload.status},
        )
        await session.flush()
        if settings.NOTIFICATIONS_ENABLED and payload.status in (
            DocumentStatus.REJECTED,
            DocumentStatus.RESUBMISSION_REQUIRED,
        ):
            application = await get_application(session, document.application_id)
            await enqueue_application_email(
                session,
                application,
                "document_requested",
                event_id=review.id,
            )
        return DocumentResponse.model_validate(document)


async def delete_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    payload: DocumentDeletion,
    actor: User,
    request: Request,
) -> DocumentResponse:
    async with application_transaction(session):
        document = await get_document(session, document_id, lock=True)
        check_editable(document, payload.expected_version)
        document.deleted_at = datetime.now(UTC)
        document.deletion_remarks = payload.remarks
        document.deleted_by = actor.id
        document.version += 1
        record_audit_event(
            session,
            request,
            actor,
            action="document.deleted",
            entity_type="document",
            entity_id=document.id,
            details={"physical_file_retained": True},
        )
        await session.flush()
        return DocumentResponse.model_validate(document)
