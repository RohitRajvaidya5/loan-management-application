from fastapi import HTTPException

from app.enums.application_status import ApplicationStatus as Status

ALLOWED_TRANSITIONS = {
    Status.NEW: frozenset({Status.CONTACTED, Status.CANCELLED}),
    Status.CONTACTED: frozenset(
        {Status.DOCUMENTS_PENDING, Status.UNDER_REVIEW, Status.CANCELLED}
    ),
    Status.DOCUMENTS_PENDING: frozenset({Status.UNDER_REVIEW, Status.CANCELLED}),
    Status.UNDER_REVIEW: frozenset(
        {
            Status.DOCUMENTS_PENDING,
            Status.SUBMITTED_TO_LENDER,
            Status.REJECTED,
            Status.CANCELLED,
        }
    ),
    Status.SUBMITTED_TO_LENDER: frozenset(
        {Status.APPROVED, Status.REJECTED, Status.CANCELLED}
    ),
    Status.APPROVED: frozenset({Status.DISBURSED, Status.CANCELLED}),
    Status.REJECTED: frozenset(),
    Status.DISBURSED: frozenset(),
    Status.CANCELLED: frozenset(),
}


def validate_transition(
    previous: Status, target: Status, remarks: str | None
) -> str | None:
    if target not in ALLOWED_TRANSITIONS[previous]:
        raise HTTPException(
            status_code=409,
            detail=f"Status transition from {previous.value} to {target.value} is not permitted.",
        )
    remarks = remarks.strip() if remarks else None
    if (
        target in {Status.REJECTED, Status.CANCELLED}
        or (previous == Status.UNDER_REVIEW and target == Status.DOCUMENTS_PENDING)
    ) and not remarks:
        raise HTTPException(
            status_code=422, detail="Remarks are required for this transition."
        )
    return remarks or None
