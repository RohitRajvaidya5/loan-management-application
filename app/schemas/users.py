from uuid import UUID

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

from app.schemas.common import ORMModel


class UserCreate(ORMModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=1024)
    role_id: UUID

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name must not be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserUpdate(ORMModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    role_id: UUID | None = None

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Full name must not be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_update_fields(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("Full name cannot be null.")
        if "email" in self.model_fields_set and self.email is None:
            raise ValueError("Email cannot be null.")
        if "role_id" in self.model_fields_set and self.role_id is None:
            raise ValueError("Role cannot be null.")
        return self


class UserResponse(ORMModel):
    id: UUID
    full_name: str
    email: EmailStr
    role_id: UUID
    is_active: bool
    is_verified: bool


class UserActiveUpdate(ORMModel):
    is_active: bool
