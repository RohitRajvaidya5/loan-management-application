from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.enums.document import DocumentStatus, DocumentType
from app.schemas.common import ORMModel


class DocumentResponse(ORMModel):
    id: UUID
    application_id: UUID
    uploaded_by: UUID | None
    document_type: str
    original_filename: str
    mime_type: str
    file_size: int = Field(ge=0)
    uploaded_at: datetime
    status: DocumentStatus
    version: int
    document_group_id: UUID
    revision: int
    replaces_document_id: UUID | None
    replaced_at: datetime | None
    verified_by: UUID | None
    verified_at: datetime | None
    review_remarks: str | None
    deleted_at: datetime | None
    deletion_remarks: str | None
    deleted_by: UUID | None


class DocumentVerification(ORMModel):
    expected_version: int = Field(ge=1)
    status: DocumentStatus
    remarks: str | None = Field(default=None, max_length=4000)

    @field_validator("remarks")
    @classmethod
    def strip_remarks(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_review(self):
        if self.status == DocumentStatus.PENDING:
            raise ValueError("Use replacement to submit a new pending revision.")
        if (
            self.status
            in (DocumentStatus.REJECTED, DocumentStatus.RESUBMISSION_REQUIRED)
            and not self.remarks
        ):
            raise ValueError("Remarks are required for rejection or resubmission.")
        return self


class DocumentDeletion(ORMModel):
    expected_version: int = Field(ge=1)
    remarks: str = Field(min_length=1, max_length=4000)

    @field_validator("remarks")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Deletion remarks must not be blank.")
        return value


class DocumentReviewResponse(ORMModel):
    id: UUID
    document_id: UUID
    reviewed_by: UUID
    previous_status: DocumentStatus
    status: DocumentStatus
    remarks: str | None
    document_version: int
    reviewed_at: datetime


class RequirementInput(ORMModel):
    document_type: DocumentType
    is_required: bool


class RequirementsUpdate(ORMModel):
    requirements: list[RequirementInput] = Field(max_length=8)

    @model_validator(mode="after")
    def no_duplicates(self):
        names = [item.document_type for item in self.requirements]
        if len(set(names)) != len(names):
            raise ValueError("Each document type may appear only once.")
        return self


class RequirementStatus(RequirementInput):
    uploaded: bool
    verified: bool


class ApplicationDocumentRequirements(ORMModel):
    application_id: UUID
    loan_type_id: UUID
    configured: bool
    requirements: list[RequirementStatus]
    missing_required: list[DocumentType]
    unverified_required: list[DocumentType]
    complete: bool
    verified_complete: bool
