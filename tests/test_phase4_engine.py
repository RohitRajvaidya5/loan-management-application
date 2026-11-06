from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.enums.application_status import ApplicationStatus as Status
from app.enums.employment_type import EmploymentType
from app.schemas.applications import (
    ApplicationAssignment,
    ApplicationStatusUpdate,
    LoanApplicationCreate,
    LoanApplicationUpdate,
)
from app.schemas.emi import EMICalculationRequest
from app.services.application_status_service import validate_transition
from app.services.emi_calculator import calculate_emi

TRANSITIONS = {
    "NEW": {"CONTACTED", "CANCELLED"},
    "CONTACTED": {"DOCUMENTS_PENDING", "UNDER_REVIEW", "CANCELLED"},
    "DOCUMENTS_PENDING": {"UNDER_REVIEW", "CANCELLED"},
    "UNDER_REVIEW": {
        "DOCUMENTS_PENDING",
        "SUBMITTED_TO_LENDER",
        "REJECTED",
        "CANCELLED",
    },
    "SUBMITTED_TO_LENDER": {"APPROVED", "REJECTED", "CANCELLED"},
    "APPROVED": {"DISBURSED", "CANCELLED"},
    "REJECTED": set(),
    "DISBURSED": set(),
    "CANCELLED": set(),
}


@pytest.mark.parametrize("previous", list(Status))
@pytest.mark.parametrize("target", list(Status))
def test_every_status_transition(previous, target):
    if target.value in TRANSITIONS[previous.value]:
        assert validate_transition(previous, target, "  Checked  ") == "Checked"
    else:
        with pytest.raises(HTTPException) as error:
            validate_transition(previous, target, "Checked")
        assert error.value.status_code == 409


@pytest.mark.parametrize(
    ("previous", "target"),
    [
        (Status.NEW, Status.CANCELLED),
        (Status.UNDER_REVIEW, Status.REJECTED),
        (Status.SUBMITTED_TO_LENDER, Status.REJECTED),
        (Status.UNDER_REVIEW, Status.DOCUMENTS_PENDING),
    ],
)
@pytest.mark.parametrize("remarks", [None, "", "  "])
def test_sensitive_transitions_require_remarks(previous, target, remarks):
    with pytest.raises(HTTPException) as error:
        validate_transition(previous, target, remarks)
    assert error.value.status_code == 422


@pytest.mark.parametrize("employment_type", list(EmploymentType))
def test_employment_types_are_accepted(employment_type):
    payload = LoanApplicationCreate(
        customer_id=uuid4(),
        loan_type_id=uuid4(),
        requested_amount="500000.00",
        tenure_months=60,
        employment_type=employment_type,
        monthly_income="60000.00",
    )
    assert payload.employment_type == employment_type


def test_unknown_employment_rejected_on_create_and_patch():
    with pytest.raises(ValidationError):
        LoanApplicationCreate(
            customer_id=uuid4(),
            loan_type_id=uuid4(),
            requested_amount=1,
            tenure_months=1,
            employment_type="INVALID",
        )
    with pytest.raises(ValidationError):
        LoanApplicationUpdate(expected_version=1, employment_type="INVALID")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LoanApplicationUpdate(purpose="changed"),
        lambda: LoanApplicationUpdate(expected_version=1),
        lambda: LoanApplicationUpdate(expected_version=1, tenure_months=None),
        lambda: ApplicationAssignment(assigned_to=None),
        lambda: ApplicationStatusUpdate(status="CONTACTED"),
        lambda: ApplicationStatusUpdate(expected_version=0, status="CONTACTED"),
    ],
)
def test_updates_require_version_and_valid_change(factory):
    with pytest.raises(ValidationError):
        factory()


@pytest.mark.parametrize(
    ("principal", "rate", "months", "monthly", "repayment", "interest"),
    [
        ("500000", "10", 60, "10623.52", "637411.34", "137411.34"),
        ("12000", "0", 12, "1000.00", "12000.00", "0.00"),
        ("100", "0", 3, "33.33", "100.00", "0.00"),
        ("1.01", "0", 2, "0.51", "1.01", "0.00"),
        ("100", "12", 1, "101.00", "101.00", "1.00"),
    ],
)
def test_emi_known_results(principal, rate, months, monthly, repayment, interest):
    result = calculate_emi(
        EMICalculationRequest(
            principal=principal,
            annual_interest_rate=rate,
            tenure_months=months,
        )
    )
    assert result.monthly_emi == Decimal(monthly)
    assert result.total_repayment == Decimal(repayment)
    assert result.total_interest == Decimal(interest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("principal", 0),
        ("principal", -1),
        ("principal", "NaN"),
        ("principal", "Infinity"),
        ("principal", "0.001"),
        ("annual_interest_rate", -1),
        ("annual_interest_rate", 101),
        ("annual_interest_rate", "NaN"),
        ("tenure_months", 0),
        ("tenure_months", 601),
    ],
)
def test_emi_rejects_invalid_values(field, value):
    payload = {"principal": "1000", "annual_interest_rate": "10", "tenure_months": 12}
    payload[field] = value
    with pytest.raises(ValidationError):
        EMICalculationRequest(**payload)


def test_emi_handles_small_rate_without_loss_of_precision():
    result = calculate_emi(
        EMICalculationRequest(
            principal="9999999999999.99",
            annual_interest_rate="0.000001",
            tenure_months=600,
        )
    )
    assert result.total_interest > 0
    assert result.total_repayment > result.principal
