import asyncio
import csv
import io
import os
import runpy
import smtplib
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx2 as httpx
import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import HTTPException
from sqlalchemy import event, func, insert, select, text, update
from starlette.requests import Request
from test_document_api import make_upload
from test_phase4_postgres import isolated_database
from test_phase6_postgres import install_session_override

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.security import hash_password
from app.database.seed import seed_initial_data
from app.enums.application_status import ApplicationStatus as Status
from app.main import app
from app.models import (
    ApplicationStatusHistory,
    AuditLog,
    Customer,
    LoanApplication,
    LoginRateLimit,
    Notification,
    Role,
    User,
)
from app.repositories import report_repository as reports
from app.schemas.reports import ReportFilters
from app.services.loan_application_service import (
    submit_application,
)
from app.services.notification_service import enqueue_application_email
from app.services.notification_worker import process_one
from app.services.rate_limit import limit_login_attempts
from app.services.storage_service import LocalDocumentStorage, get_document_storage

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Requires dedicated TEST_DATABASE_URL.",
)


async def seed(sessions):
    async with sessions() as session:
        await seed_initial_data(session)
        await session.commit()


def test_report_aggregates_filters_rates_and_processing():
    asyncio.run(_report_aggregates())


async def _report_aggregates():
    async with isolated_database() as (sessions, actor, payload):
        await seed(sessions)
        started = datetime(2026, 1, 1, tzinfo=UTC)
        async with sessions() as session:
            empty = await reports.dashboard(session, ReportFilters())
            assert empty.total_applications == 0 and empty.total_requested_amount == 0
            assert (
                await reports.statistics(session, ReportFilters())
            ).approval_rate_percent == 0
            assert (
                await reports.financial_summary(session, ReportFilters())
            ).requested_amount == 0
            for index, status in enumerate(
                [Status.NEW, Status.APPROVED, Status.DISBURSED, Status.REJECTED]
            ):
                identifier = uuid4()
                session.add(
                    LoanApplication(
                        id=identifier,
                        application_number=f"REPORT-{index}",
                        customer_id=payload.customer_id,
                        loan_type_id=payload.loan_type_id,
                        requested_amount=Decimal((index + 1) * 100),
                        tenure_months=12,
                        status=status,
                        assigned_to=actor.id,
                        created_at=started,
                    )
                )
                await session.flush()
                session.add(
                    ApplicationStatusHistory(
                        application_id=identifier,
                        old_status=Status.NEW,
                        new_status=Status.CONTACTED,
                        changed_by=actor.id,
                        created_at=started + timedelta(days=1),
                    )
                )
                if status in (Status.APPROVED, Status.DISBURSED, Status.REJECTED):
                    target = Status.APPROVED if status == Status.DISBURSED else status
                    session.add(
                        ApplicationStatusHistory(
                            application_id=identifier,
                            old_status=Status.UNDER_REVIEW,
                            new_status=target,
                            changed_by=actor.id,
                            created_at=started + timedelta(days=3),
                        )
                    )
                if status == Status.DISBURSED:
                    session.add(
                        ApplicationStatusHistory(
                            application_id=identifier,
                            old_status=Status.APPROVED,
                            new_status=Status.DISBURSED,
                            changed_by=actor.id,
                            created_at=started + timedelta(days=5),
                        )
                    )
            await session.commit()
        filters = ReportFilters(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 1),
            loan_type_id=payload.loan_type_id,
        )
        async with sessions() as session:
            application = await session.scalar(
                select(LoanApplication).where(LoanApplication.status == Status.NEW)
            )
            application.purpose = "Changed without changing submission cohort"
            await session.commit()
            await session.refresh(application)
            assert application.created_at == started
            assert application.updated_at > started
            summary = await reports.dashboard(session, filters)
            assert (
                summary.total_applications,
                summary.approved,
                summary.rejected,
                summary.disbursed,
            ) == (4, 2, 1, 1)
            assert summary.total_requested_amount == Decimal("1000.00")
            assert (
                summary.total_approved_amount is None
                and not summary.actual_amounts_available
            )
            statistics = await reports.statistics(session, filters)
            assert statistics.approval_rate_percent == Decimal("50.00")
            assert statistics.rejection_rate_percent == Decimal("25.00")
            assert [(group.key, group.count) for group in statistics.by_month] == [
                ("2026-01", 4)
            ]
            financial = await reports.financial_summary(session, filters)
            assert (
                financial.requested_amount == 1000
                and financial.disbursed_amount is None
            )
            types = await reports.loan_type_report(session, filters, 1, 1)
            assert types.total == 1 and types.items[0].requested_amount == 1000
            staff = await reports.staff_report(session, filters, 1, 100)
            member = next(item for item in staff.items if item.user_id == actor.id)
            assert (
                member.assigned,
                member.pending,
                member.approved,
                member.disbursed,
            ) == (4, 2, 2, 1)
            assert (
                member.average_processing_days == 4
            )  # rejection (3) and disbursement (5)
            processing = await reports.processing_report(
                session, filters, 0, None, 1, 1
            )
            assert processing.average_submission_to_contact_days == 1
            assert processing.average_submission_to_approval_days == 3
            assert processing.average_submission_to_rejection_days == 3
            assert (
                processing.pending_beyond_days == 2
                and processing.total == 2
                and len(processing.items) == 1
            )
            assert (
                await reports.dashboard(
                    session, ReportFilters(date_from=date(2026, 1, 2))
                )
            ).total_applications == 0
            assert (
                await reports.dashboard(session, ReportFilters(loan_type_id=uuid4()))
            ).total_applications == 0


def test_reporting_apis_exports_and_role_permissions():
    asyncio.run(_reporting_api())


async def _reporting_api():
    async with isolated_database() as (sessions, actor, payload):
        await seed(sessions)
        async with sessions() as session:
            customer = await session.get(Customer, payload.customer_id)
            customer.full_name = '=HYPERLINK("unsafe")'
            await session.commit()
            await submit_application(session, payload, actor, Request({"type": "http"}))
        install_session_override(sessions)
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in (
                "/dashboard/summary",
                "/dashboard/application-statistics",
                "/reports/loan-types",
                "/reports/staff-performance",
                "/reports/application-processing",
                "/reports/financial-summary",
                "/loan-types",
            ):
                result = await client.get("/api/v1" + path)
                assert result.status_code == 200, result.text
            for export in ("applications", "customers", "financial-summary"):
                result = await client.get(f"/api/v1/reports/{export}/export")
                assert result.status_code == 200, result.text
                assert result.headers["content-type"].startswith("text/csv")
                rows = list(csv.reader(io.StringIO(result.text)))
                if export == "customers":
                    assert rows[0] == ["customer_id", "full_name", "created_at"]
                    assert rows[1][1].startswith("'=")
                if export == "financial-summary":
                    assert "UNAVAILABLE" in result.text
            for params in (
                {"page_size": 101},
                {"date_from": "2026-05-01", "date_to": "2026-01-01"},
                {"loan_type_id": "invalid"},
                {"page": 0},
            ):
                assert (
                    await client.get("/api/v1/reports/loan-types", params=params)
                ).status_code == 422
            assert (
                await client.get(f"/api/v1/loan-types/{uuid4()}")
            ).status_code == 404
            async with sessions() as session:
                role_id = await session.scalar(
                    select(Role.id).where(Role.name == "loan_officer")
                )
                officer = User(
                    id=uuid4(),
                    full_name="Officer",
                    email="officer@example.com",
                    password_hash="unused",
                    role_id=role_id,
                    is_active=True,
                )
                session.add(officer)
                await session.commit()
            app.dependency_overrides[get_current_user] = lambda: officer
            assert (await client.get("/api/v1/dashboard/summary")).status_code == 200
            for path in (
                "/reports/loan-types",
                "/reports/applications/export",
                "/notifications",
            ):
                assert (await client.get("/api/v1" + path)).status_code == 403
            app.dependency_overrides[get_current_user] = lambda: actor
            async with sessions() as session:
                customer_role = await session.scalar(
                    select(Role.id).where(Role.name == "customer")
                )
                officer.role_id = customer_role
                await session.merge(officer)
                await session.commit()
            app.dependency_overrides[get_current_user] = lambda: officer
            assert (await client.get("/api/v1/dashboard/summary")).status_code == 403
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.action == "report.exported")
                )
                == 3
            )


class FakeSender:
    def __init__(self, fail=False, error_type=smtplib.SMTPException):
        self.fail = fail
        self.error_type = error_type
        self.sent = []

    def send(self, identifier, recipient, template):
        if self.fail:
            raise self.error_type("private-recipient-and-password")
        self.sent.append(identifier)
        return f"<{identifier}@fake-provider>"


@pytest.mark.parametrize("failure", [smtplib.SMTPException, TimeoutError, OSError])
def test_outbox_dedup_rollback_concurrent_workers_and_retries(
    monkeypatch, caplog, failure
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    asyncio.run(_outbox(caplog, failure))


async def _outbox(caplog, failure):
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            created = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )
            application = await session.get(LoanApplication, created.id)
            await enqueue_application_email(
                session, application, "application_submitted", audience="staff"
            )
            await session.commit()
            assert (
                await session.scalar(select(func.count()).select_from(Notification))
                == 1
            )
            await enqueue_application_email(
                session, application, "application_assigned", audience="staff"
            )
            await session.rollback()
            assert (
                await session.scalar(select(func.count()).select_from(Notification))
                == 1
            )
        sender = FakeSender()
        results = await asyncio.gather(
            *(process_one(sessions, sender) for _ in range(5))
        )
        assert sum(results) == 1 and len(sender.sent) == 1
        async with sessions() as session:
            notification = await session.scalar(select(Notification))
            assert notification.status == "SENT" and notification.retry_count == 1
            notification.status = "PENDING"
            notification.retry_count = 0
            await session.commit()
        assert await process_one(sessions, FakeSender(fail=True, error_type=failure))
        assert "private-recipient-and-password" not in caplog.text
        assert not await process_one(sessions, sender)  # backoff not elapsed
        for attempt in range(2, settings.NOTIFICATION_MAX_ATTEMPTS + 1):
            async with sessions() as session:
                await session.execute(
                    update(Notification).values(
                        available_at=datetime.now(UTC) - timedelta(seconds=1)
                    )
                )
                await session.commit()
            assert await process_one(
                sessions, FakeSender(fail=True, error_type=failure)
            )
        assert not await process_one(sessions, sender)
        async with sessions() as session:
            notification = await session.scalar(select(Notification))
            assert (
                notification.status == "FAILED"
                and notification.retry_count == settings.NOTIFICATION_MAX_ATTEMPTS
            )
            assert notification.last_error == failure.__name__
            notification.status = "PROCESSING"
            notification.lease_until = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        assert not await process_one(sessions, sender)
        async with sessions() as session:
            notification = await session.scalar(select(Notification))
            assert (
                notification.status == "FAILED"
                and notification.last_error == "LeaseExpired"
            )


def test_login_rate_limit_atomic_reset_and_api_429(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    asyncio.run(_rate_limit())


def test_expired_lease_recovery_and_stale_acknowledgement(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    asyncio.run(_lease_recovery(monkeypatch))


async def _lease_recovery(monkeypatch):
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            await submit_application(session, payload, actor, Request({"type": "http"}))
            await session.execute(
                update(Notification).values(
                    status="PROCESSING",
                    retry_count=1,
                    lease_token=uuid4(),
                    lease_until=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
            await session.commit()
        sender = FakeSender()
        assert await process_one(sessions, sender)
        async with sessions() as session:
            row = await session.scalar(select(Notification))
            assert row.status == "SENT" and row.retry_count == 2
            row.status, row.retry_count, row.sent_at = "PENDING", 0, None
            await session.commit()

        replacement_token = uuid4()

        async def change_owner_during_delivery(function, *args):
            async with sessions() as session:
                await session.execute(
                    update(Notification).values(
                        lease_token=replacement_token,
                        lease_until=datetime.now(UTC) + timedelta(minutes=5),
                    )
                )
                await session.commit()
            return function(*args)

        monkeypatch.setattr(
            "app.services.notification_worker.asyncio.to_thread",
            change_owner_during_delivery,
        )
        assert await process_one(sessions, sender)
        async with sessions() as session:
            row = await session.scalar(select(Notification))
            assert row.status == "PROCESSING" and row.sent_at is None
            assert row.lease_token == replacement_token


async def _rate_limit():
    async with isolated_database() as (sessions, _actor, _payload):
        request = Request({"type": "http", "client": ("192.0.2.1", 100)})

        async def hit():
            async with sessions() as session:
                try:
                    await limit_login_attempts(request, session)
                except HTTPException as error:
                    return error.status_code
                return 200

        results = await asyncio.gather(*(hit() for _ in range(15)))
        assert results.count(200) == 10 and results.count(429) == 5
        async with sessions() as session:
            row = await session.scalar(select(LoginRateLimit))
            assert row.attempts == 15 and "192.0.2.1" not in row.peer_digest
            row.window_start = datetime.now(UTC) - timedelta(minutes=2)
            await session.commit()
        assert await hit() == 200
        install_session_override(sessions)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("192.0.2.1", 100)),
            base_url="http://test",
        ) as client:
            for _ in range(9):
                response = await client.post(
                    "/api/v1/auth/token",
                    json={"email": "absent@example.com", "password": "wrong"},
                )
                assert response.status_code == 401
            response = await client.post(
                "/api/v1/auth/token",
                json={"email": "absent@example.com", "password": "wrong"},
            )
            assert (
                response.status_code == 429 and response.headers["retry-after"] == "60"
            )


def test_migration_round_trip_notifications_and_rate_limit():
    asyncio.run(_migration())


async def _migration():
    migration = runpy.run_path(
        str(
            Path("alembic")
            / "versions"
            / "d74b2c59f136_reports_notifications_hardening.py"
        )
    )
    async with (
        isolated_database() as (sessions, _actor, _payload),
        sessions() as session,
    ):
        connection = await session.connection()

        def cycle(sync_connection):
            with Operations.context(MigrationContext.configure(sync_connection)):
                migration["downgrade"]()
                migration["upgrade"]()

        await connection.run_sync(cycle)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Notification)) == 0
        assert (
            await session.scalar(select(func.count()).select_from(LoginRateLimit)) == 0
        )


def test_transaction_rolls_back_outbox_on_failed_submission(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    asyncio.run(_submission_failure(monkeypatch))


async def _submission_failure(monkeypatch):
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            monkeypatch.setattr(
                session,
                "commit",
                AsyncMock(side_effect=RuntimeError("simulated commit failure")),
            )
            with pytest.raises(RuntimeError, match="simulated"):
                await submit_application(
                    session, payload, actor, Request({"type": "http"})
                )
        async with sessions() as session:
            for model in (
                Notification,
                LoanApplication,
                ApplicationStatusHistory,
                AuditLog,
            ):
                assert (
                    await session.scalar(select(func.count()).select_from(model)) == 0
                )


def test_full_authenticated_lifecycle_with_documents_reports_and_mock_delivery(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    asyncio.run(_e2e(tmp_path))


async def _e2e(root):
    async with isolated_database() as (sessions, actor, payload):
        await seed(sessions)
        password = "phase-nine strong test password"
        async with sessions() as session:
            admin = await session.get(User, actor.id)
            admin.password_hash = hash_password(password)
            await session.commit()
        install_session_override(sessions)
        app.dependency_overrides[get_document_storage] = lambda: LocalDocumentStorage(
            root
        )
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (
                    await client.get("/api/v1/dashboard/summary")
                ).status_code == 401
                token = await client.post(
                    "/api/v1/auth/token",
                    json={"email": actor.email, "password": password},
                )
                assert token.status_code == 200, token.text
                client.headers["Authorization"] = (
                    "Bearer " + token.json()["access_token"]
                )
                customer = await client.post(
                    "/api/v1/customers",
                    json={
                        "full_name": "Lifecycle Customer",
                        "phone": "1234567890",
                        "email": "customer@example.com",
                    },
                )
                assert customer.status_code == 201, customer.text
                body = payload.model_dump(mode="json") | {
                    "customer_id": customer.json()["id"]
                }
                created = await client.post("/api/v1/loan-applications", json=body)
                assert created.status_code == 201, created.text
                path = "/api/v1/loan-applications/" + created.json()["id"]
                assigned = await client.patch(
                    path + "/assignment",
                    json={"assigned_to": str(actor.id), "expected_version": 1},
                )
                assert assigned.status_code == 200, assigned.text
                assert (
                    await client.post(
                        path + "/notes", json={"note": "Internal processing note"}
                    )
                ).status_code == 201
                upload = make_upload()
                document = await client.post(
                    path + "/documents",
                    data={"document_type": "PAN_CARD"},
                    files={
                        "upload": (
                            upload.filename,
                            await upload.read(),
                            upload.content_type,
                        )
                    },
                )
                assert document.status_code == 201, document.text
                identifier = document.json()["id"]
                reviewed = await client.patch(
                    f"/api/v1/documents/{identifier}/verification",
                    json={
                        "status": "RESUBMISSION_REQUIRED",
                        "expected_version": 1,
                        "remarks": "Readable copy required.",
                    },
                )
                assert reviewed.status_code == 200, reviewed.text
                for version, status in enumerate(
                    [
                        "CONTACTED",
                        "DOCUMENTS_PENDING",
                        "UNDER_REVIEW",
                        "SUBMITTED_TO_LENDER",
                        "APPROVED",
                        "DISBURSED",
                    ],
                    2,
                ):
                    response = await client.patch(
                        path + "/status",
                        json={"expected_version": version, "status": status},
                    )
                    assert response.status_code == 200, response.text
                history = await client.get(path + "/history")
                assert len(history.json()) == 7
                assert (await client.get(path + "/activity")).json()["total"] >= 12
                assert (await client.get("/api/v1/dashboard/summary")).json()[
                    "disbursed"
                ] == 1
                assert (await client.get("/api/v1/audit-logs")).status_code == 200
                notifications = await client.get(
                    "/api/v1/notifications",
                    params={"application_id": created.json()["id"]},
                )
                assert notifications.status_code == 200, notifications.text
                assert (
                    notifications.json()["total"] == 10
                )  # submit, assign, upload, document review, six status changes
                job = notifications.json()["items"][0]
                assert "event_key" not in job and "lease_token" not in job
                assert (
                    await client.post(f"/api/v1/notifications/{job['id']}/retry")
                ).status_code == 409
                async with sessions() as session:
                    await session.execute(
                        update(Notification)
                        .where(Notification.id == job["id"])
                        .values(status="FAILED", retry_count=3)
                    )
                    await session.commit()
                assert (
                    await client.post(f"/api/v1/notifications/{job['id']}/retry")
                ).status_code == 200
                assert (
                    await client.get(f"/api/v1/notifications/{job['id']}")
                ).status_code == 200
                assert (
                    await client.get(f"/api/v1/notifications/{uuid4()}")
                ).status_code == 404
            sender = FakeSender()
            while await process_one(sessions, sender):
                pass
            assert len(sender.sent) == 10
            async with sessions() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(Notification)
                        .where(Notification.status == "SENT")
                    )
                    == 10
                )
        finally:
            app.dependency_overrides.pop(get_document_storage, None)


def test_report_query_budget_basic_load_and_explain(capsys):
    asyncio.run(_performance())


def test_export_enforces_exact_5000_row_limit():
    asyncio.run(_export_limit())


async def _export_limit():
    async with isolated_database() as (sessions, actor, payload):
        await seed(sessions)
        async with sessions() as session:
            await session.execute(
                insert(LoanApplication),
                [
                    {
                        "application_number": f"EXPORT-{index}",
                        "customer_id": payload.customer_id,
                        "loan_type_id": payload.loan_type_id,
                        "requested_amount": Decimal("1.00"),
                        "tenure_months": 12,
                        "status": Status.NEW,
                    }
                    for index in range(5001)
                ],
            )
            await session.commit()
        install_session_override(sessions)
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/reports/applications/export")
            assert response.status_code == 422 and "5000" in response.json()["detail"]
            async with sessions() as session:
                row = await session.scalar(select(LoanApplication).limit(1))
                await session.delete(row)
                await session.commit()
            response = await client.get("/api/v1/reports/applications/export")
            assert response.status_code == 200
            assert (
                len(list(csv.reader(io.StringIO(response.text)))) == 5001
            )  # header + exactly 5000 rows


async def _performance():
    async with isolated_database() as (sessions, _actor, payload):
        async with sessions() as session:
            await session.execute(
                insert(LoanApplication),
                [
                    {
                        "application_number": f"PERF-{index}",
                        "customer_id": payload.customer_id,
                        "loan_type_id": payload.loan_type_id,
                        "requested_amount": Decimal("1000.25"),
                        "tenure_months": 12,
                        "status": Status.NEW,
                    }
                    for index in range(1200)
                ],
            )
            await session.commit()
            engine = session.bind
            statements = []

            def capture(conn, cursor, statement, params, context, many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                result = await reports.dashboard(session, ReportFilters())
                assert result.total_requested_amount == Decimal("1200300.00")
                assert len(statements) == 1
                statements.clear()
                await reports.staff_report(session, ReportFilters(), 1, 50)
                assert len(statements) == 2
                statements.clear()
                await reports.statistics(session, ReportFilters())
                assert len(statements) == 5
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)
            plan = await session.scalars(
                text(
                    "EXPLAIN (ANALYZE, BUFFERS) SELECT count(*), sum(requested_amount) FROM loan_applications"
                )
            )
            assert "Execution Time" in "\n".join(plan)

        async def request():
            started = time.perf_counter()
            async with sessions() as session:
                await reports.dashboard(session, ReportFilters())
            return (time.perf_counter() - started) * 1000

        timings = await asyncio.gather(*(request() for _ in range(20)))
        p95 = sorted(timings)[18]
        print(
            f"Local PostgreSQL: 1200 applications, 20 concurrent summary queries, p95={p95:.2f}ms"
        )
        assert (
            p95 < 5000
        )  # Regression ceiling on development hardware, not a production SLO.
