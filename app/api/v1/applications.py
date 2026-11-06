from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.enums.application_status import ApplicationStatus
from app.models import (
    ApplicationNote,
    ApplicationStatusHistory,
    LoanApplication,
    User,
)
from app.repositories.application_note_repository import get_note
from app.schemas.applications import (
    ApplicationAssignment,
    ApplicationNoteCreate,
    ApplicationNoteResponse,
    ApplicationStatusUpdate,
    LoanApplicationCreate,
    LoanApplicationResponse,
    LoanApplicationUpdate,
    StatusHistoryResponse,
)
from app.schemas.common import Page
from app.schemas.emi import EMICalculationRequest, EMICalculationResponse
from app.services import loan_application_service
from app.services.application_note_service import create_note
from app.services.emi_calculator import calculate_emi
from app.services.loan_application_service import submit_application

router = APIRouter()
STAFF_ROLES = ("administrator", "loan_officer", "underwriter")
staff_user = require_role(*STAFF_ROLES)


def _application_options():
    return (
        joinedload(LoanApplication.customer),
        joinedload(LoanApplication.loan_type),
        joinedload(LoanApplication.assigned_user),
    )


async def _get_application(
    session: AsyncSession, application_id: UUID
) -> LoanApplication:
    result = await session.execute(
        select(LoanApplication)
        .options(*_application_options())
        .where(LoanApplication.id == application_id)
    )
    application = result.unique().scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found.")
    return application


@router.post(
    "/emi",
    response_model=EMICalculationResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:read")),
    ],
)
def calculate_application_emi(payload: EMICalculationRequest) -> EMICalculationResponse:
    return calculate_emi(payload)


@router.post(
    "",
    response_model=LoanApplicationResponse,
    status_code=201,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:create")),
    ],
)
async def create_application(
    payload: LoanApplicationCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> LoanApplicationResponse:
    return await submit_application(session, payload, actor, request)


@router.get(
    "",
    response_model=Page[LoanApplicationResponse],
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:read")),
    ],
)
async def list_applications(
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    customer_id: UUID | None = None,
    assigned_to: UUID | None = None,
    reference: Annotated[str | None, Query(min_length=1, max_length=30)] = None,
    loan_type_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page[LoanApplicationResponse]:
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=422,
            detail="Page must be positive and page_size must be between 1 and 100.",
        )

    filters = []
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must not be after date_to."
        )
    if reference is not None:
        filters.append(
            LoanApplication.application_number.ilike(
                "%"
                + reference.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
                + "%",
                escape="\\",
            )
        )
    if loan_type_id is not None:
        filters.append(LoanApplication.loan_type_id == loan_type_id)
    if date_from is not None:
        filters.append(
            LoanApplication.created_at >= datetime.combine(date_from, time.min, UTC)
        )
    if date_to is not None:
        if date_to == date.max:
            filters.append(
                LoanApplication.created_at <= datetime.combine(date_to, time.max, UTC)
            )
        else:
            filters.append(
                LoanApplication.created_at
                < datetime.combine(date_to + timedelta(days=1), time.min, UTC)
            )
    if status_filter is not None:
        filters.append(LoanApplication.status == status_filter)
    if customer_id is not None:
        filters.append(LoanApplication.customer_id == customer_id)
    if assigned_to is not None:
        filters.append(LoanApplication.assigned_to == assigned_to)
    total = (
        await session.scalar(
            select(func.count()).select_from(LoanApplication).where(*filters)
        )
        or 0
    )
    result = await session.execute(
        select(LoanApplication)
        .options(*_application_options())
        .where(*filters)
        .order_by(LoanApplication.created_at.desc(), LoanApplication.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=list(result.unique().scalars().all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{application_id}",
    response_model=LoanApplicationResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:read")),
    ],
)
async def get_application(
    application_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LoanApplication:
    return await _get_application(session, application_id)


@router.patch(
    "/{application_id}",
    response_model=LoanApplicationResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:update")),
    ],
)
async def update_application(
    application_id: UUID,
    payload: LoanApplicationUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> LoanApplicationResponse:
    return await loan_application_service.update_application(
        session, application_id, payload, actor, request
    )


@router.patch(
    "/{application_id}/assignment",
    response_model=LoanApplicationResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:assign")),
    ],
)
async def assign_application(
    application_id: UUID,
    payload: ApplicationAssignment,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> LoanApplicationResponse:
    return await loan_application_service.assign_application(
        session, application_id, payload, actor, request
    )


@router.patch(
    "/{application_id}/status",
    response_model=LoanApplicationResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:status_update")),
    ],
)
async def update_application_status(
    application_id: UUID,
    payload: ApplicationStatusUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> LoanApplicationResponse:
    return await loan_application_service.change_status(
        session, application_id, payload, actor, request
    )


@router.get(
    "/{application_id}/status-history",
    response_model=list[StatusHistoryResponse],
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("loan_applications:read")),
    ],
)
async def get_application_status_history(
    application_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationStatusHistory]:
    await _get_application(session, application_id)
    result = await session.scalars(
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
    )
    return list(result.all())


@router.post(
    "/{application_id}/notes",
    response_model=ApplicationNoteResponse,
    status_code=201,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("application_notes:create")),
    ],
)
async def create_application_note(
    application_id: UUID,
    payload: ApplicationNoteCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> ApplicationNoteResponse:
    return await create_note(session, application_id, payload, actor, request)


@router.get(
    "/{application_id}/notes",
    response_model=Page[ApplicationNoteResponse],
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("application_notes:read")),
    ],
)
async def list_application_notes(
    application_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
    sort: Literal["asc", "desc"] = "desc",
) -> Page[ApplicationNoteResponse]:
    await _get_application(session, application_id)
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=422,
            detail="Page must be positive and page_size must be between 1 and 100.",
        )
    filters = [ApplicationNote.application_id == application_id]
    total = (
        await session.scalar(
            select(func.count()).select_from(ApplicationNote).where(*filters)
        )
        or 0
    )
    result = await session.scalars(
        select(ApplicationNote)
        .where(*filters)
        .order_by(
            ApplicationNote.created_at.asc()
            if sort == "asc"
            else ApplicationNote.created_at.desc(),
            ApplicationNote.id.asc() if sort == "asc" else ApplicationNote.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(items=list(result.all()), total=total, page=page, page_size=page_size)


@router.get(
    "/{application_id}/notes/{note_id}",
    response_model=ApplicationNoteResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("application_notes:read")),
    ],
)
async def get_application_note(
    application_id: UUID,
    note_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationNote:
    await _get_application(session, application_id)
    note = await get_note(session, application_id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Application note not found.")
    return note
