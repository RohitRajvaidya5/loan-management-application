from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.models import Customer, User
from app.schemas.common import Page
from app.schemas.customers import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.audit import record_audit_event

router = APIRouter()
STAFF_ROLES = ("administrator", "loan_officer", "underwriter")
staff_user = require_role(*STAFF_ROLES)


async def _get_customer(session: AsyncSession, customer_id: UUID) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return customer


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("customers:create")),
    ],
)
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> Customer:
    customer = Customer(
        **{
            key: str(value) if key == "email" and value is not None else value
            for key, value in payload.model_dump().items()
        }
    )
    session.add(customer)
    await session.flush()
    record_audit_event(
        session,
        request,
        actor,
        action="customer.created",
        entity_type="customer",
        entity_id=customer.id,
    )
    await session.commit()
    await session.refresh(customer)
    return customer


@router.get(
    "",
    response_model=Page[CustomerResponse],
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("customers:read")),
        Depends(require_permission("customers:search")),
    ],
)
async def list_customers(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    city: str | None = None,
    state: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page[CustomerResponse]:
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=422,
            detail="Page must be positive and page_size must be between 1 and 100.",
        )

    filters = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Customer.full_name.ilike(term),
                Customer.email.ilike(term),
                Customer.phone.ilike(term),
            )
        )
    if city:
        filters.append(Customer.city.ilike(f"%{city.strip()}%"))
    if state:
        filters.append(Customer.state.ilike(f"%{state.strip()}%"))

    statement = select(Customer).where(*filters)
    total = (
        await session.scalar(select(func.count()).select_from(Customer).where(*filters))
        or 0
    )
    result = await session.scalars(
        statement.order_by(Customer.created_at.desc(), Customer.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=list(result.all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("customers:read")),
    ],
)
async def get_customer(
    customer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Customer:
    return await _get_customer(session, customer_id)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[
        Depends(staff_user),
        Depends(require_permission("customers:update")),
    ],
)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(staff_user)],
) -> Customer:
    customer = await _get_customer(session, customer_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("email") is not None:
        updates["email"] = str(updates["email"])
    for field, value in updates.items():
        setattr(customer, field, value)
    await session.flush()
    record_audit_event(
        session,
        request,
        actor,
        action="customer.updated",
        entity_type="customer",
        entity_id=customer.id,
        details={"fields": sorted(updates)},
    )
    await session.commit()
    await session.refresh(customer)
    return customer
