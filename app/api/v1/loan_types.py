from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.models import LoanType
from app.schemas.common import ORMModel


class LoanTypeResponse(ORMModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool


router = APIRouter(
    dependencies=[
        Depends(require_role("administrator", "loan_officer", "underwriter")),
        Depends(require_permission("loan_applications:read")),
    ]
)


@router.get("", response_model=list[LoanTypeResponse])
async def list_loan_types(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    return list(
        await session.scalars(
            select(LoanType)
            .where(LoanType.is_active.is_(True))
            .order_by(LoanType.name, LoanType.id)
            .limit(limit)
        )
    )


@router.get("/{loan_type_id}", response_model=LoanTypeResponse)
async def get_loan_type(
    loan_type_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]
):
    loan_type = await session.get(LoanType, loan_type_id)
    if loan_type is None:
        raise HTTPException(status_code=404, detail="Loan type not found.")
    return loan_type
