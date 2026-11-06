from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Customer, LoanApplication, LoanType


async def get_customer(session: AsyncSession, customer_id: UUID) -> Customer | None:
    return await session.get(Customer, customer_id)


async def get_loan_type(session: AsyncSession, loan_type_id: UUID) -> LoanType | None:
    return await session.get(LoanType, loan_type_id)


async def add_application(session: AsyncSession, application: LoanApplication) -> None:
    session.add(application)
    await session.flush()


async def get_application(
    session: AsyncSession, application_id: UUID, *, lock: bool = False
) -> LoanApplication | None:
    statement = (
        select(LoanApplication)
        .options(
            joinedload(LoanApplication.customer),
            joinedload(LoanApplication.loan_type),
            joinedload(LoanApplication.assigned_user),
        )
        .where(LoanApplication.id == application_id)
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update(of=LoanApplication)
    result = await session.execute(statement)
    return result.unique().scalar_one_or_none()
