from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.enums.application_status import ApplicationStatus
from app.schemas.common import ORMModel


class ReportFilters(ORMModel):
    date_from: date | None = None
    date_to: date | None = None
    loan_type_id: UUID | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to.")
        return self


class DashboardSummary(ORMModel):
    total_applications: int
    total_customers: int
    active_users: int
    awaiting_review: int
    approved: int
    rejected: int
    disbursed: int
    total_requested_amount: Decimal
    total_approved_amount: Decimal | None = None
    actual_amounts_available: bool = False


class CountGroup(ORMModel):
    key: str
    count: int


class ApplicationStatistics(ORMModel):
    total: int
    approved: int
    rejected: int
    approval_rate_percent: Decimal
    rejection_rate_percent: Decimal
    by_status: list[CountGroup]
    by_loan_type: list[CountGroup]
    by_employment_type: list[CountGroup]
    by_month: list[CountGroup]


class LoanTypeReport(ORMModel):
    loan_type_id: UUID
    name: str
    total: int
    approved: int
    rejected: int
    requested_amount: Decimal
    approved_amount: Decimal | None = None


class StaffPerformance(ORMModel):
    user_id: UUID
    name: str
    assigned: int
    pending: int
    approved: int
    rejected: int
    disbursed: int
    average_processing_days: Decimal | None


class ProcessingItem(ORMModel):
    application_id: UUID
    reference: str
    status: ApplicationStatus
    pending_days: Decimal
    days_in_status: Decimal


class ProcessingReport(ORMModel):
    average_submission_to_contact_days: Decimal | None
    average_submission_to_approval_days: Decimal | None
    average_submission_to_rejection_days: Decimal | None
    pending_beyond_days: int
    threshold_days: int = Field(ge=0)
    items: list[ProcessingItem]
    total: int
    page: int
    page_size: int


class FinancialGroup(ORMModel):
    key: str
    requested_amount: Decimal
    approved_amount: Decimal | None = None
    disbursed_amount: Decimal | None = None


class FinancialSummary(ORMModel):
    requested_amount: Decimal
    approved_amount: Decimal | None = None
    disbursed_amount: Decimal | None = None
    actual_amounts_available: bool = False
    by_loan_type: list[FinancialGroup]
    by_month: list[FinancialGroup]
