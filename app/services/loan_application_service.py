from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.application_status import ApplicationStatus
from app.models import ApplicationStatusHistory, LoanApplication, Role, User
from app.repositories import loan_application_repository as repository
from app.schemas.applications import (
    ApplicationAssignment,
    ApplicationStatusUpdate,
    LoanApplicationCreate,
    LoanApplicationResponse,
    LoanApplicationUpdate,
)
from app.services.application_reference import generate_reference
from app.services.application_status_service import validate_transition
from app.services.audit import record_audit_event
from app.services.notification_service import enqueue_application_email


async def submit_application(
    session: AsyncSession,
    payload: LoanApplicationCreate,
    actor: User,
    request: Request,
) -> LoanApplicationResponse:
    customer = await repository.get_customer(session, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    loan_type = await repository.get_loan_type(session, payload.loan_type_id)
    if loan_type is None or not loan_type.is_active:
        raise HTTPException(status_code=404, detail="Active loan type not found.")

    async with application_transaction(session):
        application = LoanApplication(
            application_number=await generate_reference(session),
            **payload.model_dump(),
            status=ApplicationStatus.NEW,
        )
        await repository.add_application(session, application)
        session.add(
            ApplicationStatusHistory(
                application_id=application.id,
                old_status=None,
                new_status=ApplicationStatus.NEW,
                changed_by=actor.id,
                remarks="Application created.",
            )
        )
        record_audit_event(
            session,
            request,
            actor,
            action="loan_application.created",
            entity_type="loan_application",
            entity_id=application.id,
        )
        await session.flush()
        saved_application = await repository.get_application(session, application.id)
        if saved_application is None:
            raise RuntimeError("Submitted application could not be reloaded.")
        response = LoanApplicationResponse.model_validate(saved_application)
        await enqueue_application_email(
            session, saved_application, "application_submitted", audience="staff"
        )
    return response


@asynccontextmanager
async def application_transaction(session: AsyncSession) -> AsyncGenerator[None]:
    committed = False
    try:
        yield
        await session.commit()
        committed = True
    finally:
        if not committed:
            await session.rollback()


async def get_editable_application(
    session: AsyncSession, application_id: UUID, expected_version: int
) -> LoanApplication:
    application = await repository.get_application(session, application_id, lock=True)
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found.")
    if application.version != expected_version:
        raise HTTPException(
            status_code=409, detail="Application has changed. Reload it and retry."
        )
    return application


async def _finish_update(
    session: AsyncSession,
    application: LoanApplication,
    actor: User,
    request: Request,
    action: str,
    details: dict[str, object],
) -> LoanApplicationResponse:
    application.version += 1
    record_audit_event(
        session,
        request,
        actor,
        action=action,
        entity_type="loan_application",
        entity_id=application.id,
        details=details,
    )
    await session.flush()
    saved = await repository.get_application(session, application.id)
    if saved is None:
        raise RuntimeError("Updated application could not be reloaded.")
    return LoanApplicationResponse.model_validate(saved)


async def update_application(
    session: AsyncSession,
    application_id: UUID,
    payload: LoanApplicationUpdate,
    actor: User,
    request: Request,
) -> LoanApplicationResponse:
    async with application_transaction(session):
        application = await get_editable_application(
            session, application_id, payload.expected_version
        )
        updates = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
        if payload.loan_type_id is not None:
            loan_type = await repository.get_loan_type(session, payload.loan_type_id)
            if loan_type is None or not loan_type.is_active:
                raise HTTPException(
                    status_code=404, detail="Active loan type not found."
                )
        for field, value in updates.items():
            setattr(application, field, value)
        return await _finish_update(
            session,
            application,
            actor,
            request,
            "loan_application.updated",
            {"fields": sorted(updates)},
        )


async def assign_application(
    session: AsyncSession,
    application_id: UUID,
    payload: ApplicationAssignment,
    actor: User,
    request: Request,
) -> LoanApplicationResponse:
    async with application_transaction(session):
        application = await get_editable_application(
            session, application_id, payload.expected_version
        )
        if payload.assigned_to is not None:
            assignee_id = await session.scalar(
                select(User.id)
                .join(Role, User.role_id == Role.id)
                .where(
                    User.id == payload.assigned_to,
                    User.is_active.is_(True),
                    Role.name.in_(("administrator", "loan_officer", "underwriter")),
                )
            )
            if assignee_id is None:
                raise HTTPException(
                    status_code=404, detail="Active staff user not found."
                )
        application.assigned_to = payload.assigned_to
        response = await _finish_update(
            session,
            application,
            actor,
            request,
            "loan_application.assigned",
            {"assigned_to": str(payload.assigned_to) if payload.assigned_to else None},
        )
        await enqueue_application_email(
            session, application, "application_assigned", audience="assignee"
        )
        return response


async def change_status(
    session: AsyncSession,
    application_id: UUID,
    payload: ApplicationStatusUpdate,
    actor: User,
    request: Request,
) -> LoanApplicationResponse:
    async with application_transaction(session):
        application = await get_editable_application(
            session, application_id, payload.expected_version
        )
        previous = application.status
        remarks = validate_transition(previous, payload.status, payload.remarks)
        application.status = payload.status
        session.add(
            ApplicationStatusHistory(
                application_id=application.id,
                old_status=previous,
                new_status=payload.status,
                changed_by=actor.id,
                remarks=remarks,
            )
        )
        response = await _finish_update(
            session,
            application,
            actor,
            request,
            "loan_application.status_updated",
            {"old_status": previous.value, "new_status": payload.status.value},
        )
        event = {
            ApplicationStatus.DOCUMENTS_PENDING: "document_requested",
            ApplicationStatus.APPROVED: "application_approved",
            ApplicationStatus.REJECTED: "application_rejected",
            ApplicationStatus.DISBURSED: "application_disbursed",
        }.get(payload.status, "status_updated")
        await enqueue_application_email(session, application, event)
        return response
