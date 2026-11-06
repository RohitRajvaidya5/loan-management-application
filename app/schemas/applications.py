from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.enums.application_status import ApplicationStatus
from app.enums.employment_type import EmploymentType
from app.schemas.common import ORMModel


class LoanApplicationCreate(ORMModel):
    customer_id: UUID
    loan_type_id: UUID
    requested_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    tenure_months: int = Field(gt=0, le=600)
    employment_type: EmploymentType | None = None
    monthly_income: Decimal | None = Field(
        default=None, gt=0, max_digits=15, decimal_places=2
    )
    purpose: str | None = None


class LoanApplicationUpdate(ORMModel):
    expected_version: int = Field(ge=1)
    loan_type_id: UUID | None = None
    requested_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=15, decimal_places=2
    )
    tenure_months: int | None = Field(default=None, gt=0, le=600)
    employment_type: EmploymentType | None = None
    monthly_income: Decimal | None = Field(
        default=None, gt=0, max_digits=15, decimal_places=2
    )
    purpose: str | None = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "LoanApplicationUpdate":
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("At least one field must be provided.")
        if "loan_type_id" in self.model_fields_set and self.loan_type_id is None:
            raise ValueError("Loan type cannot be null.")
        if (
            "requested_amount" in self.model_fields_set
            and self.requested_amount is None
        ):
            raise ValueError("Requested amount cannot be null.")
        if "tenure_months" in self.model_fields_set and self.tenure_months is None:
            raise ValueError("Tenure cannot be null.")
        return self


class ApplicationAssignment(ORMModel):
    expected_version: int = Field(ge=1)
    assigned_to: UUID | None


class ApplicationStatusUpdate(ORMModel):
    expected_version: int = Field(ge=1)
    status: ApplicationStatus
    remarks: str | None = Field(default=None, max_length=2000)


class LoanTypeSummary(ORMModel):
    id: UUID
    name: str


class CustomerSummary(ORMModel):
    id: UUID
    full_name: str


class UserSummary(ORMModel):
    id: UUID
    full_name: str


class LoanApplicationResponse(ORMModel):
    id: UUID
    version: int
    application_number: str
    customer_id: UUID
    loan_type_id: UUID
    assigned_to: UUID | None
    requested_amount: Decimal
    tenure_months: int
    employment_type: str | None
    monthly_income: Decimal | None
    purpose: str | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    customer: CustomerSummary
    loan_type: LoanTypeSummary
    assigned_user: UserSummary | None


class StatusHistoryResponse(ORMModel):
    id: UUID
    old_status: ApplicationStatus | None
    new_status: ApplicationStatus
    changed_by: UUID | None
    remarks: str | None
    created_at: datetime


class ApplicationNoteCreate(ORMModel):
    note: str = Field(min_length=1, max_length=10000)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note must not be blank.")
        return value


class ApplicationNoteResponse(ORMModel):
    id: UUID
    application_id: UUID
    author_id: UUID
    note: str
    created_at: datetime
    updated_at: datetime
