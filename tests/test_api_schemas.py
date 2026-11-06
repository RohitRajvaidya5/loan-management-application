from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database.create_admin import prompt_for_admin
from app.schemas.applications import ApplicationNoteCreate, LoanApplicationCreate
from app.schemas.customers import CustomerCreate, CustomerUpdate
from app.schemas.users import UserCreate, UserUpdate


def test_user_create_normalizes_email_and_keeps_password_secret() -> None:
    payload = UserCreate(
        full_name="  Test User ",
        email="TEST@example.com",
        password="a sufficiently long password",
        role_id=uuid4(),
    )

    assert payload.full_name == "Test User"
    assert str(payload.email) == "test@example.com"
    assert "a sufficiently long password" not in repr(payload)


def test_user_update_requires_non_null_update_fields() -> None:
    with pytest.raises(ValidationError):
        UserUpdate()
    with pytest.raises(ValidationError):
        UserUpdate(full_name=None)
    with pytest.raises(ValidationError):
        UserCreate(
            full_name="Test User",
            email=None,
            password="a sufficiently long password",
            role_id=uuid4(),
        )


def test_customer_schemas_validate_required_values_and_partial_updates() -> None:
    payload = CustomerCreate(
        full_name="Customer",
        email="customer@example.com",
        phone="123456789",
        date_of_birth=date(1990, 1, 1),
    )
    assert payload.full_name == "Customer"
    assert CustomerUpdate(city="Pune").city == "Pune"
    with pytest.raises(ValidationError):
        CustomerUpdate()
    with pytest.raises(ValidationError):
        CustomerUpdate(phone=None)
    with pytest.raises(ValidationError):
        CustomerCreate(full_name="Customer", email=123, phone="123456789")


def test_loan_application_create_validates_amount_and_tenure() -> None:
    payload = LoanApplicationCreate(
        customer_id=uuid4(),
        loan_type_id=uuid4(),
        requested_amount=Decimal("1000.00"),
        tenure_months=12,
    )
    assert payload.requested_amount == Decimal("1000.00")

    with pytest.raises(ValidationError):
        LoanApplicationCreate(
            customer_id=uuid4(),
            loan_type_id=uuid4(),
            requested_amount=Decimal(-1),
            tenure_months=0,
        )


def test_application_note_rejects_blank_content() -> None:
    with pytest.raises(ValidationError):
        ApplicationNoteCreate(note="   ")


def test_admin_bootstrap_prompts_for_and_confirms_password(monkeypatch) -> None:
    prompt_values = iter(("First Admin", "ADMIN@example.com"))
    password_values = iter(
        ("a sufficiently long password", "a sufficiently long password")
    )
    monkeypatch.setattr("builtins.input", lambda _: next(prompt_values))
    monkeypatch.setattr(
        "app.database.create_admin.getpass",
        lambda _: next(password_values),
    )
    role_id = uuid4()

    payload = prompt_for_admin(role_id)

    assert payload.full_name == "First Admin"
    assert str(payload.email) == "admin@example.com"
    assert payload.role_id == role_id
    assert "a sufficiently long password" not in repr(payload)
