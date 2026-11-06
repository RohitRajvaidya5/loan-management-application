from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import IPvAnyAddress

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    id: UUID
    user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    ip_address: IPvAnyAddress | None
    user_agent: str | None
    details: dict[str, Any] | None
    created_at: datetime
