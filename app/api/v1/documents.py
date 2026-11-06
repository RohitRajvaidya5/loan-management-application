from collections.abc import Iterator
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.core.config import settings
from app.database.session import get_db
from app.enums.document import DocumentStatus, DocumentType
from app.models import Document, DocumentRequirement, DocumentReview, LoanType, User
from app.repositories.document_repository import get_application, get_document
from app.schemas.common import Page
from app.schemas.documents import (
    ApplicationDocumentRequirements,
    DocumentDeletion,
    DocumentResponse,
    DocumentReviewResponse,
    DocumentVerification,
    RequirementInput,
    RequirementStatus,
    RequirementsUpdate,
)
from app.services import document_service
from app.services.audit import record_audit_event
from app.services.loan_application_service import application_transaction
from app.services.storage_service import DocumentStorage, get_document_storage

router = APIRouter()
staff_user = require_role("administrator", "loan_officer", "underwriter")
review_user = require_role("administrator", "underwriter")
admin_user = require_role("administrator")
Session = Annotated[AsyncSession, Depends(get_db)]
Actor = Annotated[User, Depends(staff_user)]
Storage = Annotated[DocumentStorage, Depends(get_document_storage)]
read_access = [Depends(staff_user), Depends(require_permission("documents:read"))]
upload_access = [Depends(staff_user), Depends(require_permission("documents:create"))]


@router.get("/document-types", dependencies=read_access)
def document_types():
    return {
        "document_types": list(DocumentType),
        "mime_types": ["application/pdf", "image/jpeg", "image/png"],
        "extensions": [".pdf", ".jpg", ".jpeg", ".png"],
        "max_file_size_bytes": settings.MAX_DOCUMENT_SIZE_BYTES,
    }


@router.post(
    "/loan-applications/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
    dependencies=upload_access,
)
@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
    dependencies=upload_access,
)
async def upload_application_document(
    application_id: UUID,
    request: Request,
    session: Session,
    actor: Actor,
    storage: Storage,
    document_type: Annotated[DocumentType, Form()],
    upload: Annotated[UploadFile, File()],
) -> DocumentResponse:
    return await document_service.upload_document(
        session,
        application_id,
        document_type,
        upload,
        actor,
        request,
        storage,
    )


@router.get(
    "/loan-applications/{application_id}/documents",
    response_model=Page[DocumentResponse],
    dependencies=read_access,
)
@router.get(
    "/applications/{application_id}/documents",
    response_model=Page[DocumentResponse],
    dependencies=read_access,
)
async def list_application_documents(
    application_id: UUID,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    include_history: bool = False,
) -> Page[DocumentResponse]:
    await get_application(session, application_id)
    filters = [Document.application_id == application_id]
    if not include_history:
        filters.extend([Document.replaced_at.is_(None), Document.deleted_at.is_(None)])
    total = (
        await session.scalar(select(func.count()).select_from(Document).where(*filters))
        or 0
    )
    documents = await session.scalars(
        select(Document)
        .where(*filters)
        .order_by(Document.uploaded_at.desc(), Document.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[DocumentResponse.model_validate(item) for item in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    dependencies=read_access,
)
async def document_details(document_id: UUID, session: Session) -> DocumentResponse:
    return DocumentResponse.model_validate(await get_document(session, document_id))


@router.get(
    "/documents/{document_id}/revisions",
    response_model=list[DocumentResponse],
    dependencies=read_access,
)
async def document_revisions(document_id: UUID, session: Session):
    document = await get_document(session, document_id)
    revisions = await session.scalars(
        select(Document)
        .where(Document.document_group_id == document.document_group_id)
        .order_by(Document.revision, Document.id)
    )
    return list(revisions)


@router.get(
    "/documents/{document_id}/reviews",
    response_model=list[DocumentReviewResponse],
    dependencies=read_access,
)
async def document_reviews(document_id: UUID, session: Session):
    await get_document(session, document_id)
    reviews = await session.scalars(
        select(DocumentReview)
        .where(DocumentReview.document_id == document_id)
        .order_by(DocumentReview.reviewed_at, DocumentReview.id)
    )
    return list(reviews)


def _chunks(stream: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := stream.read(64 * 1024):
            yield chunk
    finally:
        stream.close()


@router.get(
    "/documents/{document_id}/download",
    dependencies=read_access,
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
@router.get(
    "/documents/{document_id}/content",
    dependencies=read_access,
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
async def download_document(
    document_id: UUID,
    request: Request,
    session: Session,
    actor: Actor,
    storage: Storage,
) -> StreamingResponse:
    document = await get_document(session, document_id, lock=True)
    if document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document content not found.")
    stream = await storage.open(document.storage_key)
    handed_off = False
    try:
        record_audit_event(
            session,
            request,
            actor,
            action="document.downloaded",
            entity_type="document",
            entity_id=document.id,
        )
        await session.commit()
        response = StreamingResponse(
            _chunks(stream),
            media_type=document.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.original_filename, safe='')}",
                "Content-Length": str(document.file_size),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
        handed_off = True
        return response
    finally:
        if not handed_off:
            stream.close()
            await session.rollback()


@router.patch(
    "/documents/{document_id}/verification",
    response_model=DocumentResponse,
    dependencies=[
        Depends(review_user),
        Depends(require_permission("documents:verify")),
    ],
)
async def verify_document(
    document_id: UUID,
    payload: DocumentVerification,
    request: Request,
    session: Session,
    actor: Actor,
):
    return await document_service.verify_document(
        session, document_id, payload, actor, request
    )


@router.post(
    "/documents/{document_id}/replacement",
    response_model=DocumentResponse,
    status_code=201,
    dependencies=upload_access,
)
async def replace_document(
    document_id: UUID,
    request: Request,
    session: Session,
    actor: Actor,
    storage: Storage,
    document_type: Annotated[DocumentType, Form()],
    expected_version: Annotated[int, Form(ge=1)],
    upload: Annotated[UploadFile, File()],
):
    previous = await get_document(session, document_id)
    return await document_service.upload_document(
        session,
        previous.application_id,
        document_type,
        upload,
        actor,
        request,
        storage,
        replaces_id=document_id,
        expected_version=expected_version,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    dependencies=[Depends(admin_user), Depends(require_permission("documents:delete"))],
)
async def delete_document(
    document_id: UUID,
    payload: DocumentDeletion,
    request: Request,
    session: Session,
    actor: Actor,
):
    return await document_service.delete_document(
        session, document_id, payload, actor, request
    )


@router.get(
    "/loan-types/{loan_type_id}/document-requirements",
    response_model=list[RequirementInput],
    dependencies=read_access,
)
async def loan_document_requirements(loan_type_id: UUID, session: Session):
    if await session.get(LoanType, loan_type_id) is None:
        raise HTTPException(status_code=404, detail="Loan type not found.")
    return list(
        await session.scalars(
            select(DocumentRequirement)
            .where(DocumentRequirement.loan_type_id == loan_type_id)
            .order_by(DocumentRequirement.document_type)
        )
    )


@router.put(
    "/loan-types/{loan_type_id}/document-requirements",
    response_model=list[RequirementInput],
    dependencies=[
        Depends(admin_user),
        Depends(require_permission("documents:configure")),
    ],
)
async def configure_requirements(
    loan_type_id: UUID,
    payload: RequirementsUpdate,
    request: Request,
    session: Session,
    actor: Actor,
):
    async with application_transaction(session):
        loan_type = await session.scalar(
            select(LoanType).where(LoanType.id == loan_type_id).with_for_update()
        )
        if loan_type is None:
            raise HTTPException(status_code=404, detail="Loan type not found.")
        await session.execute(
            delete(DocumentRequirement).where(
                DocumentRequirement.loan_type_id == loan_type_id
            )
        )
        for requirement in payload.requirements:
            session.add(
                DocumentRequirement(
                    loan_type_id=loan_type_id, **requirement.model_dump()
                )
            )
        loan_type.document_requirements_configured = True
        record_audit_event(
            session,
            request,
            actor,
            action="document_requirements.updated",
            entity_type="loan_type",
            entity_id=loan_type_id,
            details=payload.model_dump(mode="json"),
        )
    return payload.requirements


@router.get(
    "/loan-applications/{application_id}/document-requirements",
    response_model=ApplicationDocumentRequirements,
    dependencies=read_access,
)
@router.get(
    "/applications/{application_id}/document-requirements",
    response_model=ApplicationDocumentRequirements,
    dependencies=read_access,
)
async def application_requirements(application_id: UUID, session: Session):
    application = await get_application(session, application_id)
    loan_type = await session.get(LoanType, application.loan_type_id)
    requirements = await loan_document_requirements(application.loan_type_id, session)
    documents = list(
        await session.scalars(
            select(Document).where(
                Document.application_id == application_id,
                Document.deleted_at.is_(None),
                Document.replaced_at.is_(None),
            )
        )
    )
    uploaded = {item.document_type for item in documents}
    verified = {
        item.document_type
        for item in documents
        if item.status == DocumentStatus.VERIFIED
    }
    items = [
        RequirementStatus(
            document_type=item.document_type,
            is_required=item.is_required,
            uploaded=item.document_type in uploaded,
            verified=item.document_type in verified,
        )
        for item in requirements
    ]
    missing = [
        item.document_type for item in items if item.is_required and not item.uploaded
    ]
    unverified = [
        item.document_type for item in items if item.is_required and not item.verified
    ]
    configured = loan_type is not None and loan_type.document_requirements_configured
    return ApplicationDocumentRequirements(
        application_id=application_id,
        loan_type_id=application.loan_type_id,
        configured=configured,
        requirements=items,
        missing_required=missing,
        unverified_required=unverified,
        complete=configured and not missing,
        verified_complete=configured and not unverified,
    )
