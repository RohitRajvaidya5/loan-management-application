import ipaddress
from typing import Any
from uuid import UUID

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.enums.audit import AuditAction
from app.models import AuditLog, User
from app.schemas.audit_details import (
    ApplicationFields,
    AssignmentDetails,
    CustomerFields,
    DocumentDeletionDetails,
    DocumentReviewDetails,
    DocumentUploadDetails,
    EmptyDetails,
    NoteDetails,
    ReportExportDetails,
    RequirementsDetails,
    RoleChangeDetails,
    RoleDetails,
    StatusDetails,
    UserFields,
)

DETAIL_SCHEMAS = {
    AuditAction.USER_CREATED: ("user", RoleDetails),
    AuditAction.USER_UPDATED: ("user", UserFields),
    AuditAction.USER_ACTIVATED: ("user", EmptyDetails),
    AuditAction.USER_DEACTIVATED: ("user", EmptyDetails),
    AuditAction.USER_ROLE_CHANGED: ("user", RoleChangeDetails),
    AuditAction.PASSWORD_CHANGED: ("user", EmptyDetails),
    AuditAction.LOGIN_SUCCESS: ("user", EmptyDetails),
    AuditAction.LOGIN_FAILED: ("authentication", EmptyDetails),
    AuditAction.LOGOUT: ("user", EmptyDetails),
    AuditAction.CUSTOMER_CREATED: ("customer", EmptyDetails),
    AuditAction.CUSTOMER_UPDATED: ("customer", CustomerFields),
    AuditAction.APPLICATION_CREATED: ("loan_application", EmptyDetails),
    AuditAction.APPLICATION_UPDATED: ("loan_application", ApplicationFields),
    AuditAction.APPLICATION_ASSIGNED: ("loan_application", AssignmentDetails),
    AuditAction.APPLICATION_STATUS_CHANGED: ("loan_application", StatusDetails),
    AuditAction.NOTE_CREATED: ("application_note", NoteDetails),
    AuditAction.DOCUMENT_UPLOADED: ("document", DocumentUploadDetails),
    AuditAction.DOCUMENT_REPLACED: ("document", DocumentUploadDetails),
    AuditAction.DOCUMENT_REVIEWED: ("document", DocumentReviewDetails),
    AuditAction.DOCUMENT_DELETED: ("document", DocumentDeletionDetails),
    AuditAction.DOCUMENT_DOWNLOADED: ("document", EmptyDetails),
    AuditAction.REQUIREMENTS_UPDATED: ("loan_type", RequirementsDetails),
    AuditAction.REPORT_EXPORTED: ("report", ReportExportDetails),
    AuditAction.NOTIFICATION_RETRIED: ("notification", EmptyDetails),
}


def record_audit_event(
    session: AsyncSession,
    request: Request,
    user: User | None,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    action = AuditAction(action)
    expected_entity, detail_schema = DETAIL_SCHEMAS[action]
    if entity_type != expected_entity:
        raise ValueError(f"Invalid entity type for {action}.")
    try:
        validated = detail_schema.model_validate(details or {}).model_dump(mode="json")
    except ValidationError:
        raise ValueError(f"Invalid audit details for {action}.") from None
    headers = Headers(raw=request.scope.get("headers", []))
    client_host = request.client.host if request.client else None
    try:
        ip_address = str(ipaddress.ip_address(client_host)) if client_host else None
    except ValueError:
        ip_address = None

    session.add(
        AuditLog(
            user_id=user.id if user is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent="".join(
                char
                for char in headers.get("user-agent", "")[:512]
                if 32 <= ord(char) != 127
            )
            or None,
            details=validated or None,
        )
    )
