from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Numeric, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.application_status import ApplicationStatus as Status
from app.models import (
    ApplicationStatusHistory,
    Customer,
    LoanApplication,
    LoanType,
    Role,
    User,
)
from app.schemas.common import Page
from app.schemas.reports import (
    ApplicationStatistics,
    CountGroup,
    DashboardSummary,
    FinancialGroup,
    FinancialSummary,
    LoanTypeReport,
    ProcessingItem,
    ProcessingReport,
    ReportFilters,
    StaffPerformance,
)

A = LoanApplication
APPROVED = (Status.APPROVED, Status.DISBURSED)
TERMINAL = (Status.REJECTED, Status.DISBURSED, Status.CANCELLED)
MAX_REPORT_GROUPS = 5000


def check_group_limit(count: int) -> None:
    if count > MAX_REPORT_GROUPS:
        raise HTTPException(
            status_code=422,
            detail="Report exceeds 5000 groups. Narrow the date range or loan type.",
        )


def application_filters(filters: ReportFilters):
    conditions = []
    if filters.loan_type_id is not None:
        conditions.append(A.loan_type_id == filters.loan_type_id)
    if filters.date_from is not None:
        conditions.append(
            A.created_at >= datetime.combine(filters.date_from, time.min, UTC)
        )
    if filters.date_to is not None:
        upper = datetime.combine(filters.date_to, time.max, UTC)
        if filters.date_to == date.max:
            conditions.append(A.created_at <= upper)
        else:
            conditions.append(
                A.created_at
                < datetime.combine(filters.date_to + timedelta(days=1), time.min, UTC)
            )
    return conditions


def status_count(*statuses: Status):
    return func.count(A.id).filter(A.status.in_(statuses))


def money_total():
    return func.coalesce(func.sum(A.requested_amount), Decimal("0.00"))


def first_status_times():
    return (
        select(
            ApplicationStatusHistory.application_id.label("application_id"),
            func.min(ApplicationStatusHistory.created_at)
            .filter(ApplicationStatusHistory.new_status == Status.CONTACTED)
            .label("contacted"),
            func.min(ApplicationStatusHistory.created_at)
            .filter(ApplicationStatusHistory.new_status == Status.APPROVED)
            .label("approved"),
            func.min(ApplicationStatusHistory.created_at)
            .filter(ApplicationStatusHistory.new_status == Status.REJECTED)
            .label("rejected"),
            func.min(ApplicationStatusHistory.created_at)
            .filter(ApplicationStatusHistory.new_status.in_(TERMINAL))
            .label("completed"),
            func.max(ApplicationStatusHistory.created_at).label("last_changed"),
        )
        .group_by(ApplicationStatusHistory.application_id)
        .subquery()
    )


def days_between(end, start):
    return cast(func.extract("epoch", end - start) / 86400, Numeric(18, 4))


async def dashboard(session: AsyncSession, filters: ReportFilters) -> DashboardSummary:
    row = (
        (
            await session.execute(
                select(
                    func.count(A.id).label("total_applications"),
                    status_count(Status.DOCUMENTS_PENDING, Status.UNDER_REVIEW).label(
                        "awaiting_review"
                    ),
                    status_count(*APPROVED).label("approved"),
                    status_count(Status.REJECTED).label("rejected"),
                    status_count(Status.DISBURSED).label("disbursed"),
                    money_total().label("total_requested_amount"),
                    select(func.count())
                    .select_from(Customer)
                    .scalar_subquery()
                    .label("total_customers"),
                    select(func.count())
                    .select_from(User)
                    .where(User.is_active.is_(True))
                    .scalar_subquery()
                    .label("active_users"),
                ).where(*application_filters(filters))
            )
        )
        .mappings()
        .one()
    )
    return DashboardSummary.model_validate(dict(row))


async def statistics(
    session: AsyncSession, filters: ReportFilters
) -> ApplicationStatistics:
    conditions = application_filters(filters)
    counts = (
        await session.execute(
            select(
                func.count(A.id), status_count(*APPROVED), status_count(Status.REJECTED)
            ).where(*conditions)
        )
    ).one()

    async def grouped(column) -> list[CountGroup]:
        rows = await session.execute(
            select(column, func.count())
            .select_from(A)
            .where(*conditions)
            .group_by(column)
            .order_by(column)
            .limit(MAX_REPORT_GROUPS + 1)
        )
        result = [
            CountGroup(key=str(key) if key is not None else "UNSPECIFIED", count=count)
            for key, count in rows
        ]
        check_group_limit(len(result))
        return result

    total, approved, rejected = counts
    return ApplicationStatistics(
        total=total,
        approved=approved,
        rejected=rejected,
        approval_rate_percent=(Decimal(approved * 100) / total).quantize(Decimal(".01"))
        if total
        else Decimal("0.00"),
        rejection_rate_percent=(Decimal(rejected * 100) / total).quantize(
            Decimal(".01")
        )
        if total
        else Decimal("0.00"),
        by_status=await grouped(A.status),
        by_loan_type=await grouped(A.loan_type_id),
        by_employment_type=await grouped(A.employment_type),
        by_month=await grouped(
            func.to_char(func.timezone("UTC", A.created_at), "YYYY-MM")
        ),
    )


async def loan_type_report(
    session: AsyncSession, filters: ReportFilters, page: int, page_size: int
) -> Page[LoanTypeReport]:
    grouped = (
        select(
            A.loan_type_id.label("loan_type_id"),
            func.count(A.id).label("total"),
            status_count(*APPROVED).label("approved"),
            status_count(Status.REJECTED).label("rejected"),
            money_total().label("requested_amount"),
        )
        .where(*application_filters(filters))
        .group_by(A.loan_type_id)
        .subquery()
    )
    statement = select(
        LoanType.id.label("loan_type_id"),
        LoanType.name,
        func.coalesce(grouped.c.total, 0).label("total"),
        func.coalesce(grouped.c.approved, 0).label("approved"),
        func.coalesce(grouped.c.rejected, 0).label("rejected"),
        func.coalesce(grouped.c.requested_amount, Decimal("0.00")).label(
            "requested_amount"
        ),
    ).outerjoin(grouped, grouped.c.loan_type_id == LoanType.id)
    if filters.loan_type_id:
        statement = statement.where(LoanType.id == filters.loan_type_id)
    total = (
        await session.scalar(select(func.count()).select_from(statement.subquery()))
        or 0
    )
    rows = (
        await session.execute(
            statement.order_by(LoanType.name, LoanType.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).mappings()
    return Page(
        items=[LoanTypeReport.model_validate(dict(row)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def staff_report(
    session: AsyncSession, filters: ReportFilters, page: int, page_size: int
) -> Page[StaffPerformance]:
    history = first_status_times()
    grouped = (
        select(
            A.assigned_to.label("user_id"),
            func.count(A.id).label("assigned"),
            func.count(A.id).filter(A.status.not_in(TERMINAL)).label("pending"),
            status_count(*APPROVED).label("approved"),
            status_count(Status.REJECTED).label("rejected"),
            status_count(Status.DISBURSED).label("disbursed"),
            func.avg(days_between(history.c.completed, A.created_at)).label(
                "average_processing_days"
            ),
        )
        .outerjoin(history, history.c.application_id == A.id)
        .where(*application_filters(filters))
        .group_by(A.assigned_to)
        .subquery()
    )
    statement = (
        select(
            User.id.label("user_id"),
            User.full_name.label("name"),
            *(
                func.coalesce(grouped.c[name], 0).label(name)
                for name in ("assigned", "pending", "approved", "rejected", "disbursed")
            ),
            grouped.c.average_processing_days,
        )
        .join(Role, Role.id == User.role_id)
        .outerjoin(grouped, grouped.c.user_id == User.id)
        .where(Role.name.in_(("administrator", "loan_officer", "underwriter")))
    )
    total = (
        await session.scalar(select(func.count()).select_from(statement.subquery()))
        or 0
    )
    rows = (
        await session.execute(
            statement.order_by(User.full_name, User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).mappings()
    return Page(
        items=[StaffPerformance.model_validate(dict(row)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def processing_report(
    session: AsyncSession,
    filters: ReportFilters,
    threshold_days: int,
    status: Status | None,
    page: int,
    page_size: int,
) -> ProcessingReport:
    history = first_status_times()
    base = (
        select(A, history)
        .outerjoin(history, history.c.application_id == A.id)
        .where(*application_filters(filters))
    )
    if status is not None:
        base = base.where(A.status == status)
    source = base.subquery()
    averages = (
        await session.execute(
            select(
                *(
                    func.avg(days_between(source.c[name], source.c.created_at))
                    for name in ("contacted", "approved", "rejected")
                )
            )
        )
    ).one()
    pending_days = days_between(func.now(), source.c.created_at)
    days_in_status = days_between(
        func.now(), func.coalesce(source.c.last_changed, source.c.created_at)
    )
    pending = and_(source.c.status.not_in(TERMINAL), pending_days > threshold_days)
    pending_count = (
        await session.scalar(select(func.count()).select_from(source).where(pending))
        or 0
    )
    total = (
        await session.scalar(
            select(func.count())
            .select_from(source)
            .where(source.c.status.not_in(TERMINAL), days_in_status > threshold_days)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(
                source.c.id.label("application_id"),
                source.c.application_number.label("reference"),
                source.c.status,
                pending_days.label("pending_days"),
                days_in_status.label("days_in_status"),
            )
            .where(source.c.status.not_in(TERMINAL), days_in_status > threshold_days)
            .order_by(days_in_status.desc(), source.c.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).mappings()
    return ProcessingReport(
        average_submission_to_contact_days=averages[0],
        average_submission_to_approval_days=averages[1],
        average_submission_to_rejection_days=averages[2],
        pending_beyond_days=pending_count,
        threshold_days=threshold_days,
        items=[ProcessingItem.model_validate(dict(row)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def financial_summary(
    session: AsyncSession, filters: ReportFilters
) -> FinancialSummary:
    conditions = application_filters(filters)
    total = await session.scalar(select(money_total()).where(*conditions))

    async def groups(column):
        rows = await session.execute(
            select(column, money_total())
            .where(*conditions)
            .group_by(column)
            .order_by(column)
            .limit(MAX_REPORT_GROUPS + 1)
        )
        result = [
            FinancialGroup(key=str(key), requested_amount=amount)
            for key, amount in rows
        ]
        check_group_limit(len(result))
        return result

    return FinancialSummary(
        requested_amount=total,
        by_loan_type=await groups(A.loan_type_id),
        by_month=await groups(
            func.to_char(func.timezone("UTC", A.created_at), "YYYY-MM")
        ),
    )
