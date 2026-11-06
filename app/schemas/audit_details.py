from typing import Literal
from uuid import UUID

from pydantic import Field

from app.enums.application_status import ApplicationStatus
from app.enums.document import DocumentStatus, DocumentType
from app.schemas.common import ORMModel
from app.schemas.documents import RequirementInput


class EmptyDetails(ORMModel):
    pass


class RoleDetails(ORMModel):
    role_id: UUID


class RoleChangeDetails(ORMModel):
    previous_role_id: UUID
    role_id: UUID


class UserFields(ORMModel):
    fields: list[Literal["full_name", "email", "role_id"]] = Field(max_length=3)


class CustomerFields(ORMModel):
    fields: list[
        Literal[
            "full_name",
            "email",
            "phone",
            "alternate_phone",
            "date_of_birth",
            "address",
            "city",
            "state",
            "pincode",
        ]
    ] = Field(max_length=20)


class ApplicationFields(ORMModel):
    fields: list[
        Literal[
            "loan_type_id",
            "requested_amount",
            "tenure_months",
            "employment_type",
            "monthly_income",
            "purpose",
        ]
    ] = Field(max_length=10)


class AssignmentDetails(ORMModel):
    assigned_to: UUID | None


class StatusDetails(ORMModel):
    old_status: ApplicationStatus
    new_status: ApplicationStatus


class NoteDetails(ORMModel):
    application_id: UUID


class DocumentUploadDetails(ORMModel):
    application_id: UUID
    document_type: DocumentType
    file_size: int = Field(ge=0)
    replaces_document_id: UUID | None = None


class DocumentReviewDetails(ORMModel):
    previous_status: DocumentStatus
    status: DocumentStatus


class DocumentDeletionDetails(ORMModel):
    physical_file_retained: Literal[True]


class RequirementsDetails(ORMModel):
    requirements: list[RequirementInput] = Field(max_length=8)


class ReportExportDetails(ORMModel):
    report: Literal["applications", "customers", "financial-summary"]
    rows: int = Field(ge=0, le=5000)
