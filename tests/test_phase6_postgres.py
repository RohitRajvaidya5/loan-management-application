import asyncio
import json
import os
import runpy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx2 as httpx
import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from test_document_api import make_upload
from test_phase4_postgres import isolated_database

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    token_digest,
    verify_password,
)
from app.database.seed import seed_initial_data
from app.database.session import get_db
from app.enums.audit import AuditAction
from app.enums.document import DocumentType
from app.main import app
from app.models import (
    ApplicationNote,
    AuditLog,
    Permission,
    RevokedToken,
    Role,
    User,
    role_permissions,
)
from app.schemas.applications import ApplicationNoteCreate
from app.services.application_note_service import create_note
from app.services.document_service import upload_document
from app.services.loan_application_service import submit_application
from app.services.storage_service import LocalDocumentStorage

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 for Phase 6 PostgreSQL tests.",
)
PASSWORD = "phase6 valid password"


async def setup_activity(sessions, actor, payload):
    async with sessions() as session:
        await seed_initial_data(session)
        user = await session.get(User, actor.id)
        user.password_hash = hash_password(PASSWORD)
        await session.commit()
        return await submit_application(
            session, payload, actor, Request({"type": "http"})
        )


def install_session_override(sessions):
    async def override_get_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db


def current_user_override(user):
    def override():
        return user

    return override


def test_notes_timeline_search_and_pagination(tmp_path):
    asyncio.run(_notes_and_timeline(tmp_path))


async def _notes_and_timeline(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_activity(sessions, actor, payload)
        install_session_override(sessions)
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            path = f"/api/v1/loan-applications/{created.id}"
            legacy = f"/api/v1/applications/{created.id}"
            note_text = "Customer requested two additional days."
            note = await client.post(path + "/notes", json={"note": note_text})
            assert note.status_code == 201, note.text
            note_id = note.json()["id"]
            assert note.json()["author_id"] == str(actor.id)
            assert (await client.get(path + f"/notes/{note_id}")).json() == note.json()
            assert (await client.get(legacy + f"/notes/{note_id}")).status_code == 200
            assert (
                await client.get(f"/api/v1/loan-applications/{uuid4()}/notes/{note_id}")
            ).status_code == 404
            assert (await client.get(path + f"/notes/{uuid4()}")).status_code == 404
            assert (
                await client.post(path + "/notes", json={"note": " "})
            ).status_code == 422
            assert (
                await client.patch(path + f"/notes/{note_id}", json={"note": "edit"})
            ).status_code == 405
            assert (await client.delete(path + f"/notes/{note_id}")).status_code == 405
            second = await client.post(
                legacy + "/notes", json={"note": "Follow-up completed."}
            )
            assert second.status_code == 201
            listing = await client.get(
                path + "/notes", params={"sort": "asc", "page_size": 1}
            )
            assert (
                listing.json()["total"] == 2
                and listing.json()["items"][0]["id"] == note_id
            )
            listing = await client.get(
                legacy + "/notes", params={"sort": "desc", "page_size": 1}
            )
            assert listing.json()["items"][0]["id"] == second.json()["id"]
            for body in ({"page": 0}, {"page_size": 101}, {"sort": "invalid"}):
                assert (
                    await client.get(path + "/notes", params=body)
                ).status_code == 422
            changed = await client.patch(
                path + "/status",
                json={
                    "expected_version": 1,
                    "status": "CONTACTED",
                    "remarks": "Reached customer.",
                },
            )
            assert changed.status_code == 200
            async with sessions() as session:
                document = await upload_document(
                    session,
                    created.id,
                    DocumentType.PAN_CARD,
                    make_upload(),
                    actor,
                    Request({"type": "http"}),
                    LocalDocumentStorage(root),
                )
            timeline = await client.get(path + "/activity")
            assert timeline.status_code == 200, timeline.text
            events = timeline.json()["items"]
            assert (
                len(events) == 6
            )  # creation audit, initial status, 2 notes, status, upload
            assert {event["source"] for event in events} == {
                "note",
                "status_history",
                "audit",
            }
            assert [event["occurred_at"] for event in events] == sorted(
                event["occurred_at"] for event in events
            )
            assert all(
                event["actor_id"] == str(actor.id)
                and event["actor_name"] == actor.full_name
                for event in events
            )
            assert sum(event["source"] == "note" for event in events) == 2
            assert sum(event["source"] == "status_history" for event in events) == 2
            assert next(
                event for event in events if event["action"] == "document.uploaded"
            )["document_id"] == str(document.id)
            assert not any(
                key in event
                for event in events
                for key in ("details", "ip_address", "user_agent")
            )
            reverse = (
                await client.get(legacy + "/activity", params={"sort": "desc"})
            ).json()["items"]
            assert reverse == list(reversed(events))
            pages = []
            for page in (1, 2, 3):
                response = await client.get(
                    path + "/activity", params={"page": page, "page_size": 2}
                )
                assert response.json()["total"] == 6
                pages.extend(response.json()["items"])
            assert pages == events
            today = datetime.now(UTC).date().isoformat()
            query = {
                "user_id": str(actor.id),
                "entity_type": "application_note",
                "entity_id": note_id,
                "action": "application_note.created",
                "date_from": today,
                "date_to": today,
                "sort": "asc",
                "page_size": 1,
            }
            audit = await client.get("/api/v1/audit-logs", params=query)
            assert audit.status_code == 200, audit.text
            assert audit.json()["total"] == 1
            assert note_text not in audit.text
            assert audit.json()["items"][0]["details"] == {
                "application_id": str(created.id)
            }
            for field, value in (
                ("user_id", str(uuid4())),
                ("entity_id", str(uuid4())),
                ("entity_type", "not_found"),
                ("action", "not_found"),
                ("date_from", "1900-01-01"),  # paired with date_to below
            ):
                params = {**query, field: value}
                if field == "date_from":
                    params["date_to"] = "1900-01-01"
                response = await client.get("/api/v1/audit-logs", params=params)
                assert response.status_code == 200 and response.json()["total"] == 0
            for params in (
                {"date_from": "2026-02-02", "date_to": "2026-01-01"},
                {"page": 0},
                {"page_size": 101},
                {"sort": "bad"},
            ):
                assert (
                    await client.get("/api/v1/audit-logs", params=params)
                ).status_code == 422
            assert (
                await client.get("/api/v1/audit-logs", params={"date_to": "9999-12-31"})
            ).status_code == 200
            assert set((await client.get("/api/v1/audit-logs/actions")).json()) == set(
                AuditAction
            )
            assert (
                await client.patch("/api/v1/audit-logs", json={})
            ).status_code == 405
            assert (await client.delete("/api/v1/audit-logs")).status_code == 405


def test_login_logout_password_changes_and_private_audit_metadata():
    asyncio.run(_authentication_activity())


async def _authentication_activity():
    async with isolated_database() as (sessions, actor, payload):
        await setup_activity(sessions, actor, payload)
        install_session_override(sessions)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for email in (actor.email, "unknown@example.com"):
                failed = await client.post(
                    "/api/v1/auth/token",
                    json={"email": email, "password": "do-not-log-this"},
                )
                assert failed.status_code == 401
            success = await client.post(
                "/api/v1/auth/token",
                json={"email": actor.email, "password": PASSWORD},
                headers={
                    "User-Agent": "phase6-test-agent",
                    "X-Forwarded-For": "192.0.2.10",
                },
            )
            assert success.status_code == 200, success.text
            first = success.json()["access_token"]
            headers = {"Authorization": f"Bearer {first}"}
            assert (
                await client.get("/api/v1/auth/me", headers=headers)
            ).status_code == 200
            # A second login produces a distinct token even within the same second.
            second_login = await client.post(
                "/api/v1/auth/token", json={"email": actor.email, "password": PASSWORD}
            )
            second = second_login.json()["access_token"]
            assert second != first
            assert (
                await client.post("/api/v1/auth/logout", headers=headers)
            ).status_code == 204
            assert (
                await client.get("/api/v1/auth/me", headers=headers)
            ).status_code == 401
            assert (
                await client.post("/api/v1/auth/logout", headers=headers)
            ).status_code == 401
            second_headers = {"Authorization": f"Bearer {second}"}
            assert (
                await client.get("/api/v1/auth/me", headers=second_headers)
            ).status_code == 200
            assert (
                await client.post(
                    "/api/v1/auth/password",
                    headers=second_headers,
                    json={
                        "current_password": "wrong",
                        "new_password": "a new strong password",
                    },
                )
            ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/auth/password",
                    headers=second_headers,
                    json={
                        "current_password": PASSWORD,
                        "new_password": PASSWORD,
                    },
                )
            ).status_code == 422
            changed = await client.post(
                "/api/v1/auth/password",
                headers=second_headers,
                json={
                    "current_password": PASSWORD,
                    "new_password": "a new strong password",
                },
            )
            assert changed.status_code == 204, changed.text
            assert (
                await client.get("/api/v1/auth/me", headers=second_headers)
            ).status_code == 401
            assert (
                await client.post(
                    "/api/v1/auth/token",
                    json={"email": actor.email, "password": PASSWORD},
                )
            ).status_code == 401
            assert (
                await client.post(
                    "/api/v1/auth/token",
                    json={"email": actor.email, "password": "a new strong password"},
                )
            ).status_code == 200
        async with sessions() as session:
            user = await session.get(User, actor.id)
            assert user.token_version == 1 and user.last_login_at is not None
            assert verify_password("a new strong password", user.password_hash)
            revoked = await session.get(RevokedToken, token_digest(first))
            assert revoked is not None and revoked.expires_at > datetime.now(UTC)
            audits = list(await session.scalars(select(AuditLog)))
            actions = [item.action for item in audits]
            assert actions.count(AuditAction.LOGIN_FAILED) == 3
            assert actions.count(AuditAction.LOGOUT) == 1
            assert actions.count(AuditAction.PASSWORD_CHANGED) == 1
            failed_events = [
                item for item in audits if item.action == AuditAction.LOGIN_FAILED
            ]
            assert all(
                item.user_id is None and item.details is None for item in failed_events
            )
            logged_in = next(
                item for item in audits if item.action == AuditAction.LOGIN_SUCCESS
            )
            assert logged_in.user_agent == "phase6-test-agent"
            assert str(logged_in.ip_address) == "127.0.0.1"
            serialized = json.dumps([item.details for item in audits])
            assert all(
                value not in serialized
                for value in (
                    PASSWORD,
                    first,
                    second,
                    actor.email,
                    "do-not-log-this",
                    "a new strong password",
                )
            )


def test_role_and_activation_changes_invalidate_tokens_and_are_audited():
    asyncio.run(_user_activity())


async def _user_activity():
    async with isolated_database() as (sessions, actor, payload):
        await setup_activity(sessions, actor, payload)
        install_session_override(sessions)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            admin_login = await client.post(
                "/api/v1/auth/token", json={"email": actor.email, "password": PASSWORD}
            )
            headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
            async with sessions() as session:
                roles = {
                    role.name: role.id for role in await session.scalars(select(Role))
                }
            created = await client.post(
                "/api/v1/users",
                headers=headers,
                json={
                    "full_name": "Phase Six Staff",
                    "email": "phase6staff@example.com",
                    "password": PASSWORD,
                    "role_id": str(roles["loan_officer"]),
                },
            )
            assert created.status_code == 201, created.text
            user_path = f"/api/v1/users/{created.json()['id']}"
            staff_login = await client.post(
                "/api/v1/auth/token",
                json={"email": "phase6staff@example.com", "password": PASSWORD},
            )
            staff_headers = {
                "Authorization": f"Bearer {staff_login.json()['access_token']}"
            }
            changed = await client.patch(
                user_path, headers=headers, json={"role_id": str(roles["underwriter"])}
            )
            assert changed.status_code == 200, changed.text
            assert (
                await client.get("/api/v1/auth/me", headers=staff_headers)
            ).status_code == 401
            login = await client.post(
                "/api/v1/auth/token",
                json={"email": "phase6staff@example.com", "password": PASSWORD},
            )
            staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            for active in (False, True):
                response = await client.patch(
                    user_path + "/activation",
                    headers=headers,
                    json={"is_active": active},
                )
                assert response.status_code == 200
            assert (
                await client.get("/api/v1/auth/me", headers=staff_headers)
            ).status_code == 401
        async with sessions() as session:
            user = await session.get(User, created.json()["id"])
            assert user.token_version == 3
            events = list(
                await session.scalars(
                    select(AuditLog).where(AuditLog.entity_id == user.id)
                )
            )
            assert {
                "user.created",
                "user.updated",
                "user.role_changed",
                "user.deactivated",
                "user.activated",
            } <= {item.action for item in events}


def test_note_and_authentication_failures_roll_back_audit_and_business_state():
    asyncio.run(_transaction_failures())


async def _transaction_failures():
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_activity(sessions, actor, payload)
        async with sessions() as session:
            roles = {role.name: role.id for role in await session.scalars(select(Role))}
            target = User(
                full_name="Rollback Staff",
                email="rollback@example.com",
                password_hash=hash_password(PASSWORD),
                role_id=roles["loan_officer"],
            )
            session.add(target)
            await session.commit()
        async with sessions() as session:
            with pytest.raises(IntegrityError):
                await create_note(
                    session,
                    created.id,
                    ApplicationNoteCreate(note="Uncommitted note"),
                    User(id=uuid4()),
                    Request({"type": "http"}),
                )
        async with sessions() as session:
            session.commit = AsyncMock(side_effect=RuntimeError("note audit failed"))
            with pytest.raises(RuntimeError, match="note audit failed"):
                await create_note(
                    session,
                    created.id,
                    ApplicationNoteCreate(note="Uncommitted note"),
                    actor,
                    Request({"type": "http"}),
                )
        token = create_access_token(
            str(actor.id), settings.JWT_SECRET_KEY.get_secret_value()
        )

        async def failing_session():
            async with sessions() as session:
                session.commit = AsyncMock(
                    side_effect=RuntimeError("audit commit failed")
                )
                yield session

        app.dependency_overrides[get_db] = failing_session
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = {"Authorization": f"Bearer {token}"}
            for path, body in (
                ("/api/v1/auth/token", {"email": actor.email, "password": PASSWORD}),
                ("/api/v1/auth/token", {"email": actor.email, "password": "wrong"}),
                ("/api/v1/auth/logout", None),
                (
                    "/api/v1/auth/password",
                    {
                        "current_password": PASSWORD,
                        "new_password": "different long password",
                    },
                ),
            ):
                failed = await client.post(path, headers=headers, json=body)
                assert failed.status_code == 500
                assert failed.json()["code"] == "INTERNAL_ERROR"
            for path, body in (
                (f"/api/v1/users/{target.id}", {"role_id": str(roles["underwriter"])}),
                (f"/api/v1/users/{target.id}/activation", {"is_active": False}),
            ):
                failed = await client.patch(path, headers=headers, json=body)
                assert failed.status_code == 500
                assert failed.json()["code"] == "INTERNAL_ERROR"
        install_session_override(sessions)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert (
                await client.get("/api/v1/auth/me", headers=headers)
            ).status_code == 200
        async with sessions() as session:
            user = await session.get(User, actor.id)
            assert user.token_version == 0 and user.last_login_at is None
            assert verify_password(PASSWORD, user.password_hash)
            saved_target = await session.get(User, target.id)
            assert saved_target.role_id == roles["loan_officer"]
            assert saved_target.is_active and saved_target.token_version == 0
            assert (
                await session.scalar(select(func.count()).select_from(ApplicationNote))
                == 0
            )
            assert (
                await session.scalar(select(func.count()).select_from(RevokedToken))
                == 0
            )
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_phase6_role_and_permission_boundaries():
    asyncio.run(_access_boundaries())


async def _access_boundaries():
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_activity(sessions, actor, payload)
        install_session_override(sessions)
        async with sessions() as session:
            roles = {role.name: role.id for role in await session.scalars(select(Role))}
            users = {}
            for name in ("loan_officer", "underwriter", "customer"):
                user = User(
                    full_name=name,
                    email=f"{name}@example.com",
                    password_hash="unused",
                    role_id=roles[name],
                )
                session.add(user)
                await session.flush()
                users[name] = user
            audit_permission = await session.scalar(
                select(Permission.id).where(Permission.name == "audit_logs:read")
            )
            await session.execute(
                role_permissions.insert().values(
                    [
                        {"role_id": roles[name], "permission_id": audit_permission}
                        for name in ("customer", "underwriter")
                    ]
                )
            )
            await session.commit()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            path = f"/api/v1/loan-applications/{created.id}"
            assert (await client.get(path + "/activity")).status_code == 401
            for name, user in users.items():
                app.dependency_overrides[get_current_user] = current_user_override(user)
                assert (await client.get("/api/v1/audit-logs")).status_code == 403
                assert (
                    await client.get("/api/v1/audit-logs/actions")
                ).status_code == 403
                expected = 403 if name == "customer" else 200
                for base in (path, f"/api/v1/applications/{created.id}"):
                    assert (
                        await client.get(base + "/activity")
                    ).status_code == expected
                    assert (await client.get(base + "/notes")).status_code == expected
                if name == "customer":
                    assert (
                        await client.post(path + "/notes", json={"note": "Denied"})
                    ).status_code == 403
            async with sessions() as session:
                notes_permission = await session.scalar(
                    select(Permission.id).where(
                        Permission.name == "application_notes:read"
                    )
                )
                await session.execute(
                    role_permissions.delete().where(
                        role_permissions.c.role_id == roles["underwriter"],
                        role_permissions.c.permission_id == notes_permission,
                    )
                )
                await session.execute(
                    role_permissions.delete().where(
                        role_permissions.c.role_id == actor.role_id,
                        role_permissions.c.permission_id == audit_permission,
                    )
                )
                await session.commit()
            app.dependency_overrides[get_current_user] = lambda: users["underwriter"]
            assert (await client.get(path + "/activity")).status_code == 403
            app.dependency_overrides[get_current_user] = lambda: actor
            assert (await client.get("/api/v1/audit-logs")).status_code == 403


def test_phase6_migration_preserves_existing_audit_and_users():
    asyncio.run(_migration_roundtrip())


async def _migration_roundtrip():
    migration = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "c63a1b48e025_activity_and_token_revocation.py"
        )
    )
    async with isolated_database() as (sessions, actor, payload):
        await setup_activity(sessions, actor, payload)
        async with sessions() as session:
            connection = await session.connection()

            def roundtrip(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration["downgrade"]()
                    migration["upgrade"]()

            await connection.run_sync(roundtrip)
            await session.commit()
            user = await session.get(User, actor.id)
            assert user.token_version == 0
            events = list(await session.scalars(select(AuditLog)))
            assert len(events) == 1 and events[0].action == "loan_application.created"
            assert events[0].user_agent is None
            assert (
                await session.scalar(select(func.count()).select_from(RevokedToken))
                == 0
            )


def test_timeline_equal_timestamp_tiebreaks_and_application_isolation():
    asyncio.run(_timeline_ties())


async def _timeline_ties():
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_activity(sessions, actor, payload)
        async with sessions() as session:
            other = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )
            await create_note(
                session,
                other.id,
                ApplicationNoteCreate(note="Other application"),
                actor,
                Request({"type": "http"}),
            )
            for note in ("First", "Second"):
                await create_note(
                    session,
                    created.id,
                    ApplicationNoteCreate(note=note),
                    actor,
                    Request({"type": "http"}),
                )
            timestamp = datetime(2026, 1, 1, tzinfo=UTC)
            await session.execute(
                text("UPDATE application_notes SET created_at = :timestamp"),
                {"timestamp": timestamp},
            )
            await session.execute(
                text("UPDATE application_status_history SET created_at = :timestamp"),
                {"timestamp": timestamp},
            )
            await session.execute(
                text("UPDATE audit_logs SET created_at = :timestamp"),
                {"timestamp": timestamp},
            )
            await session.commit()
        install_session_override(sessions)
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            path = f"/api/v1/loan-applications/{created.id}/activity"
            events = (await client.get(path)).json()
            assert events["total"] == 4
            items = events["items"]
            assert "Other application" not in json.dumps(items)
            assert [(item["source"], item["id"]) for item in items] == sorted(
                (item["source"], item["id"]) for item in items
            )
            paged = []
            for page in range(1, 5):
                paged.extend(
                    (
                        await client.get(path, params={"page": page, "page_size": 1})
                    ).json()["items"]
                )
            assert paged == items
