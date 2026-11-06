import asyncio
import os
import runpy
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import httpx2 as httpx
import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.api.v1.dependencies import get_current_user
from app.core.config import get_async_database_url
from app.database.base import Base
from app.database.session import get_db
from app.enums.application_status import ApplicationStatus
from app.main import app
from app.models import (
    ApplicationStatusHistory,
    AuditLog,
    Customer,
    LoanApplication,
    LoanType,
    Permission,
    Role,
    User,
    role_permissions,
)
from app.schemas.applications import ApplicationStatusUpdate, LoanApplicationCreate
from app.services.application_reference import generate_reference
from app.services.loan_application_service import change_status, submit_application

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run PostgreSQL lifecycle tests.",
)


@asynccontextmanager
async def isolated_database() -> AsyncGenerator[tuple]:
    schema = f"phase4_test_{uuid4().hex}"
    setup_engine = create_async_engine(get_async_database_url(), echo=False)
    test_engine = create_async_engine(
        get_async_database_url(),
        echo=False,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with setup_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                text("CREATE SEQUENCE loan_application_reference_seq")
            )
        sessions = async_sessionmaker(test_engine, expire_on_commit=False)
        async with sessions() as session:
            role = Role(name="administrator")
            customer = Customer(full_name="Phase Four Customer", phone="1234567890")
            loan_type = LoanType(name="Phase Four Loan", is_active=True)
            session.add_all([role, customer, loan_type])
            await session.flush()
            actor = User(
                full_name="Phase Four Staff",
                email="phase4@example.com",
                password_hash="unused-test-login",
                role_id=role.id,
                is_active=True,
            )
            session.add(actor)
            for name in (
                "loan_applications:create",
                "loan_applications:read",
                "loan_applications:update",
                "loan_applications:assign",
                "loan_applications:status_update",
            ):
                permission = Permission(name=name)
                session.add(permission)
                await session.flush()
                await session.execute(
                    role_permissions.insert().values(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )
            await session.commit()
        payload = LoanApplicationCreate(
            customer_id=customer.id,
            loan_type_id=loan_type.id,
            requested_amount="500000.00",
            tenure_months=60,
            employment_type="SALARIED",
            monthly_income="60000.00",
        )
        yield sessions, actor, payload
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        await test_engine.dispose()
        async with setup_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await setup_engine.dispose()


def test_concurrent_submissions_and_sequence_rollback():
    asyncio.run(_concurrent_submissions())


async def _concurrent_submissions():
    async with isolated_database() as (sessions, actor, payload):

        async def submit():
            async with sessions() as session:
                return await submit_application(
                    session, payload, actor, Request({"type": "http"})
                )

        results = await asyncio.gather(*(submit() for _ in range(10)))
        references = [result.application_number for result in results]
        assert len(set(references)) == 10
        assert all(result.version == 1 for result in results)
        numbers = sorted(int(reference.split("-")[-1]) for reference in references)
        assert numbers == list(range(1, 11))
        async with sessions() as session:
            rolled_back_reference = await generate_reference(session)
            await session.rollback()
            next_reference = await generate_reference(session)
            assert (
                int(next_reference.split("-")[-1])
                == int(rolled_back_reference.split("-")[-1]) + 1
            )
            assert (
                await session.scalar(select(func.count()).select_from(LoanApplication))
                == 10
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(ApplicationStatusHistory)
                )
                == 10
            )
            assert (
                await session.scalar(select(func.count()).select_from(AuditLog)) == 10
            )


def test_concurrent_status_updates_reject_stale_write_and_preserve_history():
    asyncio.run(_concurrent_status_changes())


async def _concurrent_status_changes():
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            created = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )

        async def change():
            async with sessions() as session:
                # Preload an old identity-map value to exercise populate_existing.
                await session.get(LoanApplication, created.id)
                try:
                    return await change_status(
                        session,
                        created.id,
                        ApplicationStatusUpdate(status="CONTACTED", expected_version=1),
                        actor,
                        Request({"type": "http"}),
                    )
                except HTTPException as error:
                    return error

        results = await asyncio.gather(change(), change())
        assert sum(not isinstance(result, HTTPException) for result in results) == 1
        errors = [result for result in results if isinstance(result, HTTPException)]
        assert errors[0].status_code == 409
        async with sessions() as session:
            application = await session.get(LoanApplication, created.id)
            assert application.version == 2
            assert application.status == ApplicationStatus.CONTACTED
            history = (
                await session.scalars(
                    select(ApplicationStatusHistory).order_by(
                        ApplicationStatusHistory.created_at
                    )
                )
            ).all()
            assert len(history) == 2
            assert history[1].old_status == ApplicationStatus.NEW
            assert history[1].new_status == ApplicationStatus.CONTACTED
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 2


def test_status_history_failure_rolls_back_status_and_version():
    asyncio.run(_history_failure())


async def _history_failure():
    from sqlalchemy.exc import IntegrityError

    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            created = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )
        async with sessions() as session:
            missing_actor = User(id=uuid4())
            with pytest.raises(IntegrityError):
                await change_status(
                    session,
                    created.id,
                    ApplicationStatusUpdate(status="CONTACTED", expected_version=1),
                    missing_actor,
                    Request({"type": "http"}),
                )
        async with sessions() as session:
            application = await session.get(LoanApplication, created.id)
            assert application.version == 1
            assert application.status == ApplicationStatus.NEW
            assert (
                await session.scalar(
                    select(func.count()).select_from(ApplicationStatusHistory)
                )
                == 1
            )
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_phase4_api_workflow_search_and_version_conflicts():
    asyncio.run(_api_workflow())


def test_engine_migration_preserves_references_and_initializes_sequence():
    asyncio.run(_migration_roundtrip())


async def _migration_roundtrip():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "a41e9b26c803_add_application_engine.py"
    )
    migration = runpy.run_path(str(migration_path))
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            created = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )
        async with sessions() as session:
            await session.execute(
                text(
                    "UPDATE loan_applications SET application_number = 'LN-2026-000100'"
                )
            )
            await session.commit()
            connection = await session.connection()

            def roundtrip(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration["downgrade"]()
                    migration["upgrade"]()

            await connection.run_sync(roundtrip)
            await session.commit()
            application = await session.get(LoanApplication, created.id)
            assert application.version == 1
            assert application.application_number == "LN-2026-000100"
            reference = await generate_reference(session)
            assert reference.endswith("-000101")


async def _api_workflow():
    async with isolated_database() as (sessions, actor, payload):

        async def override_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/loan-applications", json=payload.model_dump(mode="json")
            )
            assert response.status_code == 201, response.text
            created = response.json()
            path = f"/api/v1/loan-applications/{created['id']}"
            assert (await client.get(path)).json()["version"] == 1
            invalid = await client.patch(
                path + "/status", json={"status": "APPROVED", "expected_version": 1}
            )
            assert invalid.status_code == 409
            for index, status in enumerate(
                (
                    "CONTACTED",
                    "DOCUMENTS_PENDING",
                    "UNDER_REVIEW",
                    "SUBMITTED_TO_LENDER",
                    "APPROVED",
                    "DISBURSED",
                ),
                start=1,
            ):
                status_path = (
                    f"/api/v1/applications/{created['id']}/status"
                    if index == 1
                    else path + "/status"
                )
                changed = await client.patch(
                    status_path, json={"status": status, "expected_version": index}
                )
                assert changed.status_code == 200, changed.text
                assert changed.json()["version"] == index + 1
            terminal = await client.patch(
                path + "/status",
                json={
                    "status": "CANCELLED",
                    "expected_version": 7,
                    "remarks": "Not permitted",
                },
            )
            assert terminal.status_code == 409
            history = await client.get(path + "/history")
            assert history.status_code == 200
            assert len(history.json()) == 7
            updated = await client.patch(
                path, json={"purpose": "New purpose", "expected_version": 7}
            )
            assert updated.status_code == 200
            stale = await client.patch(
                path, json={"purpose": "Stale edit", "expected_version": 7}
            )
            assert stale.status_code == 409
            assigned = await client.patch(
                path + "/assignment",
                json={
                    "assigned_to": str(actor.id),
                    "expected_version": 8,
                },
            )
            assert assigned.status_code == 200
            assert assigned.json()["version"] == 9
            query = {
                "reference": created["application_number"],
                "status": "DISBURSED",
                "loan_type_id": str(payload.loan_type_id),
                "customer_id": str(payload.customer_id),
                "assigned_to": str(actor.id),
                "date_from": created["created_at"][:10],
                "date_to": created["created_at"][:10],
                "page_size": 1,
            }
            found = await client.get("/api/v1/loan-applications", params=query)
            assert found.status_code == 200, found.text
            assert found.json()["total"] == 1
            assert len(found.json()["items"]) == 1
            for field, value in (
                ("reference", "DOES-NOT-EXIST"),
                ("status", "NEW"),
                ("customer_id", str(uuid4())),
                ("loan_type_id", str(uuid4())),
                ("assigned_to", str(uuid4())),
            ):
                absent = await client.get(
                    "/api/v1/loan-applications", params={**query, field: value}
                )
                assert absent.status_code == 200
                assert absent.json()["total"] == 0
                assert absent.json()["items"] == []
            legacy_list = await client.get("/api/v1/applications", params=query)
            assert legacy_list.json() == found.json()
            query["page"] = 2
            assert (await client.get("/api/v1/loan-applications", params=query)).json()[
                "items"
            ] == []
            bad_dates = await client.get(
                "/api/v1/loan-applications",
                params={
                    "date_from": "2027-01-01",
                    "date_to": "2026-01-01",
                },
            )
            assert bad_dates.status_code == 422
            emi = await client.post(
                "/api/v1/loan-applications/emi",
                json={
                    "principal": "500000",
                    "annual_interest_rate": "10",
                    "tenure_months": 60,
                },
            )
            assert emi.status_code == 200
            assert emi.json()["monthly_emi"] == "10623.52"
