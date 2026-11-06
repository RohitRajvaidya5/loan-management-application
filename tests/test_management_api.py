from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.database.session import get_db
from app.enums.application_status import ApplicationStatus
from app.main import app
from app.models import (
    ApplicationStatusHistory,
    AuditLog,
    Customer,
    LoanApplication,
    LoanType,
)


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def unique(self):
        return self


def install_overrides(session, actor):
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: actor


def remove_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_create_user_and_creation_is_audited():
    role_id = uuid4()
    actor = SimpleNamespace(id=uuid4(), role_id=role_id)
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = ScalarResult(uuid4())
    session.get.return_value = SimpleNamespace(id=role_id)
    added_objects = []
    session.add.side_effect = added_objects.append

    async def flush():
        added_objects[0].id = uuid4()
        added_objects[0].is_active = True
        added_objects[0].is_verified = False

    session.flush.side_effect = flush
    install_overrides(session, actor)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/users",
                json={
                    "full_name": "New Staff User",
                    "email": "staff@example.com",
                    "password": "a sufficiently long password",
                    "role_id": str(role_id),
                },
            )
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["email"] == "staff@example.com"
        assert "password" not in response_data
        assert "password_hash" not in response_data
        created_user = added_objects[0]
        assert created_user.password_hash != "a sufficiently long password"
        assert any(isinstance(item, AuditLog) for item in added_objects)
    finally:
        remove_overrides()


def test_application_status_update_records_history_and_audit():
    actor_id = uuid4()
    now = datetime.now(UTC)
    customer = Customer(
        id=uuid4(),
        full_name="Test Customer",
        email=None,
        phone="123456789",
    )
    loan_type = LoanType(id=uuid4(), name="Personal Loan", is_active=True)
    application = LoanApplication(
        id=uuid4(),
        application_number="LA-TEST",
        customer_id=customer.id,
        loan_type_id=loan_type.id,
        requested_amount=Decimal("1000.00"),
        tenure_months=12,
        status=ApplicationStatus.NEW,
        version=1,
        created_at=now,
        updated_at=now,
        customer=customer,
        loan_type=loan_type,
        assigned_user=None,
    )
    session = AsyncMock(spec=AsyncSession)
    query_count = 0

    async def execute(statement):
        nonlocal query_count
        query_count += 1
        if query_count <= 2:
            return ScalarResult(uuid4())
        return ScalarResult(application)

    session.execute.side_effect = execute
    added_objects = []
    session.add.side_effect = added_objects.append
    install_overrides(session, SimpleNamespace(id=actor_id, role_id=uuid4()))
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/applications/{application.id}/status",
                json={
                    "status": "CONTACTED",
                    "remarks": "Customer contacted.",
                    "expected_version": 1,
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] == "CONTACTED"
        assert response.json()["version"] == 2
        history = next(
            item for item in added_objects if isinstance(item, ApplicationStatusHistory)
        )
        assert history.old_status is ApplicationStatus.NEW
        assert history.new_status is ApplicationStatus.CONTACTED
        assert history.changed_by == actor_id
        assert history.remarks == "Customer contacted."
        assert any(isinstance(item, AuditLog) for item in added_objects)
    finally:
        remove_overrides()
