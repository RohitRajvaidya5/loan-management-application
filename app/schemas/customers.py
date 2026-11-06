from datetime import date
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common import ORMModel


class CustomerCreate(ORMModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str = Field(min_length=1, max_length=20)
    alternate_phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)

    @field_validator("full_name", "phone")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class CustomerUpdate(ORMModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    alternate_phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)

    @field_validator("full_name", "phone")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_update_fields(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("Full name cannot be null.")
        if "phone" in self.model_fields_set and self.phone is None:
            raise ValueError("Phone cannot be null.")
        return self


class CustomerResponse(ORMModel):
    id: UUID
    full_name: str
    email: EmailStr | None
    phone: str
    alternate_phone: str | None
    date_of_birth: date | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
