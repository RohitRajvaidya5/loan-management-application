import csv
from datetime import date
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.enums.application_status import ApplicationStatus
from app.models import Customer, LoanApplication, User
from app.repositories import report_repository as reports
from app.schemas.common import Page
from app.schemas.reports import (
    ApplicationStatistics,
    DashboardSummary,
    FinancialSummary,
    LoanTypeReport,
    ProcessingReport,
    ReportFilters,
    StaffPerformance,
)
from app.services.audit import record_audit_event
from app.services.loan_application_service import application_transaction

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_db)]


async def report_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    loan_type_id: UUID | None = None,
) -> ReportFilters:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must not be after date_to."
        )
    return ReportFilters(
        date_from=date_from, date_to=date_to, loan_type_id=loan_type_id
    )


Filters = Annotated[ReportFilters, Depends(report_filters)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
staff = require_role("administrator", "loan_officer", "underwriter")
dashboard_access = [Depends(staff), Depends(require_permission("dashboard:read"))]
report_access = [
    Depends(require_role("administrator")),
    Depends(require_permission("reports:read")),
]
export_access = [
    Depends(require_role("administrator")),
    Depends(require_permission("reports:export")),
]
EXPORT_LIMIT = 5000


@router.get(
    "/dashboard/summary", response_model=DashboardSummary, dependencies=dashboard_access
)
async def dashboard_summary(session: Session, filters: Filters):
    """Application-cohort counts; customer/user counts are global. Actual approved amounts are unavailable."""
    return await reports.dashboard(session, filters)


@router.get(
    "/dashboard/application-statistics",
    response_model=ApplicationStatistics,
    dependencies=dashboard_access,
)
async def application_statistics(session: Session, filters: Filters):
    """Current-status statistics. Approved includes DISBURSED; rate denominator is all applications in the cohort."""
    return await reports.statistics(session, filters)


@router.get(
    "/reports/loan-types",
    response_model=Page[LoanTypeReport],
    dependencies=report_access,
)
async def loan_types_report(
    session: Session, filters: Filters, page: PageNumber = 1, page_size: PageSize = 50
):
    return await reports.loan_type_report(session, filters, page, page_size)


@router.get(
    "/reports/staff-performance",
    response_model=Page[StaffPerformance],
    dependencies=report_access,
)
async def staff_performance(
    session: Session, filters: Filters, page: PageNumber = 1, page_size: PageSize = 50
):
    """Current assignee attribution, not historical staff ownership. Completion includes rejection/disbursement/cancellation."""
    return await reports.staff_report(session, filters, page, page_size)


@router.get(
    "/reports/application-processing",
    response_model=ProcessingReport,
    dependencies=report_access,
)
async def application_processing(
    session: Session,
    filters: Filters,
    threshold_days: Annotated[int, Query(ge=0, le=36500)] = 7,
    status: ApplicationStatus | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 50,
):
    return await reports.processing_report(
        session, filters, threshold_days, status, page, page_size
    )


@router.get(
    "/reports/financial-summary",
    response_model=FinancialSummary,
    dependencies=report_access,
)
async def financial_summary(session: Session, filters: Filters):
    return await reports.financial_summary(session, filters)


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r", "\n")
    ) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def csv_response(
    headers: list[str], rows: list[list[object]], filename: str
) -> Response:
    if len(rows) > EXPORT_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"Export exceeds {EXPORT_LIMIT} rows. Narrow the date range.",
        )
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/reports/applications/export", dependencies=export_access, response_class=Response
)
async def export_applications(
    session: Session,
    filters: Filters,
    request: Request,
    actor: Annotated[User, Depends(require_role("administrator"))],
):
    rows = await session.execute(
        select(
            LoanApplication.application_number,
            LoanApplication.status,
            LoanApplication.loan_type_id,
            LoanApplication.requested_amount,
            LoanApplication.tenure_months,
            LoanApplication.created_at,
        )
        .where(*reports.application_filters(filters))
        .order_by(LoanApplication.created_at, LoanApplication.id)
        .limit(EXPORT_LIMIT + 1)
    )
    data = [list(row) for row in rows]
    response = csv_response(
        [
            "reference",
            "status",
            "loan_type_id",
            "requested_amount",
            "tenure_months",
            "created_at",
        ],
        data,
        "applications",
    )
    async with application_transaction(session):
        record_audit_event(
            session,
            request,
            actor,
            action="report.exported",
            entity_type="report",
            entity_id=None,
            details={"report": "applications", "rows": len(data)},
        )
    return response


@router.get(
    "/reports/customers/export", dependencies=export_access, response_class=Response
)
async def export_customers(
    session: Session,
    request: Request,
    actor: Annotated[User, Depends(require_role("administrator"))],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
):
    # Export only identifiers and names, never identity, address, email or banking fields.
    from datetime import UTC, date, datetime, time, timedelta

    from pydantic import ValidationError

    try:
        filters = ReportFilters(date_from=date_from, date_to=date_to)
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="Invalid customer export date range."
        ) from None
    conditions = []
    if filters.date_from:
        conditions.append(
            Customer.created_at >= datetime.combine(filters.date_from, time.min, UTC)
        )
    if filters.date_to:
        if filters.date_to == date.max:
            conditions.append(
                Customer.created_at <= datetime.combine(date.max, time.max, UTC)
            )
        else:
            conditions.append(
                Customer.created_at
                < datetime.combine(filters.date_to + timedelta(days=1), time.min, UTC)
            )
    rows = await session.execute(
        select(Customer.id, Customer.full_name, Customer.created_at)
        .where(*conditions)
        .order_by(Customer.created_at, Customer.id)
        .limit(EXPORT_LIMIT + 1)
    )
    data = [list(row) for row in rows]
    response = csv_response(
        ["customer_id", "full_name", "created_at"], data, "customers"
    )
    async with application_transaction(session):
        record_audit_event(
            session,
            request,
            actor,
            action="report.exported",
            entity_type="report",
            entity_id=None,
            details={"report": "customers", "rows": len(data)},
        )
    return response


@router.get(
    "/reports/financial-summary/export",
    dependencies=export_access,
    response_class=Response,
)
async def export_financial(
    session: Session,
    filters: Filters,
    request: Request,
    actor: Annotated[User, Depends(require_role("administrator"))],
):
    result = await reports.financial_summary(session, filters)
    rows: list[list[object]] = [
        ["total", "all", result.requested_amount, "UNAVAILABLE", "UNAVAILABLE"]
    ]
    rows.extend(
        ["loan_type", item.key, item.requested_amount, "UNAVAILABLE", "UNAVAILABLE"]
        for item in result.by_loan_type
    )
    rows.extend(
        ["month", item.key, item.requested_amount, "UNAVAILABLE", "UNAVAILABLE"]
        for item in result.by_month
    )
    response = csv_response(
        ["group", "key", "requested_amount", "approved_amount", "disbursed_amount"],
        rows,
        "financial-summary",
    )
    async with application_transaction(session):
        record_audit_event(
            session,
            request,
            actor,
            action="report.exported",
            entity_type="report",
            entity_id=None,
            details={"report": "financial-summary", "rows": len(rows)},
        )
    return response
