from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_permission, require_role
from app.database.session import get_db
from app.repositories.document_repository import get_application
from app.schemas.activity import ApplicationActivity
from app.schemas.common import Page
from app.services.activity_service import application_activity

router = APIRouter()
access = [
    Depends(require_role("administrator", "loan_officer", "underwriter")),
    Depends(require_permission("loan_applications:read")),
    Depends(require_permission("application_notes:read")),
]


@router.get(
    "/loan-applications/{application_id}/activity",
    response_model=Page[ApplicationActivity],
    dependencies=access,
)
@router.get(
    "/applications/{application_id}/activity",
    response_model=Page[ApplicationActivity],
    dependencies=access,
)
async def read_application_activity(
    application_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    sort: Literal["asc", "desc"] = "asc",
) -> Page[ApplicationActivity]:
    await get_application(session, application_id)
    return await application_activity(session, application_id, page, page_size, sort)
