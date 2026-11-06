from uuid import UUID

from pydantic import BaseModel, JsonValue


class ErrorResponse(BaseModel):
    detail: JsonValue
    code: str
    request_id: UUID
