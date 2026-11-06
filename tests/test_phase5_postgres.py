import asyncio
import os
import runpy
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx2 as httpx
import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from test_document_api import make_upload, pdf_bytes
from test_phase4_postgres import isolated_database

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.database.seed import seed_initial_data
from app.database.session import get_db
from app.enums.document import DocumentType
from app.main import app
from app.models import (
    AuditLog,
    Document,
    DocumentRequirement,
    DocumentReview,
    LoanType,
    Permission,
    Role,
    User,
    role_permissions,
)
from app.schemas.documents import DocumentVerification
from app.services.document_service import upload_document, verify_document
from app.services.loan_application_service import submit_application
from app.services.storage_service import LocalDocumentStorage

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 for document integration tests.",
)


async def setup_documents(sessions, actor, payload):
    async with sessions() as session:
        for name in (
            "documents:create",
            "documents:read",
            "documents:verify",
            "documents:delete",
            "documents:configure",
        ):
            permission = Permission(name=name)
            session.add(permission)
            await session.flush()
            await session.execute(
                role_permissions.insert().values(
                    role_id=actor.role_id,
                    permission_id=permission.id,
                )
            )
        await session.commit()
        return await submit_application(
            session, payload, actor, Request({"type": "http"})
        )


def test_document_api_full_lifecycle_and_requirements(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_PATH", tmp_path)
    asyncio.run(_api_lifecycle(tmp_path))


async def _api_lifecycle(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)

        async def override_get_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: actor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            application_path = f"/api/v1/loan-applications/{created.id}"
            configure = await client.put(
                f"/api/v1/loan-types/{payload.loan_type_id}/document-requirements",
                json={
                    "requirements": [
                        {"document_type": "PAN_CARD", "is_required": True},
                        {"document_type": "PHOTOGRAPH", "is_required": False},
                    ]
                },
            )
            assert configure.status_code == 200, configure.text
            required = await client.get(application_path + "/document-requirements")
            assert required.json()["configured"]
            assert required.json()["missing_required"] == ["PAN_CARD"]
            assert not required.json()["complete"]
            for name in ("PAN_CARD", "PHOTOGRAPH"):
                uploaded = await client.post(
                    application_path + "/documents",
                    data={"document_type": name},
                    files={"upload": ("pan.pdf", pdf_bytes(), "application/pdf")},
                )
                assert uploaded.status_code == 201, uploaded.text
                if name == "PAN_CARD":
                    first = uploaded.json()
            path = f"/api/v1/documents/{first['id']}"
            required = (
                await client.get(application_path + "/document-requirements")
            ).json()
            assert required["complete"] and not required["verified_complete"]
            details = await client.get(path)
            assert details.json() == first
            invalid = await client.patch(
                path + "/verification",
                json={
                    "expected_version": 1,
                    "status": "REJECTED",
                    "remarks": "  ",
                },
            )
            assert invalid.status_code == 422
            reviewed = await client.patch(
                path + "/verification",
                json={
                    "expected_version": 1,
                    "status": "VERIFIED",
                },
            )
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["version"] == 2
            assert reviewed.json()["verified_by"] == str(actor.id)
            assert (
                await client.get(application_path + "/document-requirements")
            ).json()["verified_complete"]
            stale = await client.patch(
                path + "/verification",
                json={
                    "expected_version": 1,
                    "status": "REJECTED",
                    "remarks": "Unreadable",
                },
            )
            assert stale.status_code == 409
            rejected = await client.patch(
                path + "/verification",
                json={
                    "expected_version": 2,
                    "status": "RESUBMISSION_REQUIRED",
                    "remarks": "Please provide a clearer copy.",
                },
            )
            assert rejected.status_code == 200
            assert rejected.json()["version"] == 3
            reviews = (await client.get(path + "/reviews")).json()
            assert [item["status"] for item in reviews] == [
                "VERIFIED",
                "RESUBMISSION_REQUIRED",
            ]
            wrong_category = await client.post(
                path + "/replacement",
                data={"document_type": "PHOTOGRAPH", "expected_version": 3},
                files={"upload": ("updated.pdf", pdf_bytes(), "application/pdf")},
            )
            assert wrong_category.status_code == 422
            replacement = await client.post(
                path + "/replacement",
                data={"document_type": "PAN_CARD", "expected_version": 3},
                files={"upload": ("updated.pdf", pdf_bytes(), "application/pdf")},
            )
            assert replacement.status_code == 201, replacement.text
            successor = replacement.json()
            assert successor["status"] == "PENDING"
            assert successor["version"] == 1 and successor["revision"] == 2
            assert successor["replaces_document_id"] == first["id"]
            assert successor["verified_by"] is None
            assert successor["document_group_id"] == first["document_group_id"]
            versions = (await client.get(path + "/revisions")).json()
            assert len(versions) == 2
            assert versions[0]["status"] == "RESUBMISSION_REQUIRED"
            assert versions[0]["version"] == 4 and versions[0]["replaced_at"]
            assert (await client.get(path + "/reviews")).json() == reviews
            repeated = await client.post(
                path + "/replacement",
                data={"document_type": "PAN_CARD", "expected_version": 3},
                files={"upload": ("updated.pdf", pdf_bytes(), "application/pdf")},
            )
            assert repeated.status_code == 409
            documents = (await client.get(application_path + "/documents")).json()
            assert documents["total"] == 2
            history = (
                await client.get(
                    application_path + "/documents", params={"include_history": True}
                )
            ).json()
            assert history["total"] == 3
            assert (await client.get(path + "/download")).status_code == 200
            new_path = f"/api/v1/documents/{successor['id']}"
            assert (await client.get(new_path + "/download")).content == pdf_bytes()
            deleted = await client.request(
                "DELETE",
                new_path,
                json={
                    "expected_version": 1,
                    "remarks": "Uploaded to the wrong application.",
                },
            )
            assert deleted.status_code == 200
            assert deleted.json()["deleted_at"]
            assert deleted.json()["deleted_by"] == str(actor.id)
            assert (await client.get(new_path + "/download")).status_code == 404
            assert (await client.get(new_path + "/content")).status_code == 404
            assert (
                await client.patch(
                    new_path + "/verification",
                    json={
                        "expected_version": 2,
                        "status": "VERIFIED",
                    },
                )
            ).status_code == 409
            assert (
                await client.request(
                    "DELETE",
                    new_path,
                    json={
                        "expected_version": 2,
                        "remarks": "Already deleted",
                    },
                )
            ).status_code == 409
            assert (await client.get(application_path + "/documents")).json()[
                "total"
            ] == 1
            required = (
                await client.get(application_path + "/document-requirements")
            ).json()
            assert required["missing_required"] == ["PAN_CARD"]
            assert not required["complete"]
            # Soft deletion retains every historical file, never overwriting bytes.
            assert len(list(root.rglob("*.pdf"))) == 3
            legacy = await client.get(f"/api/v1/applications/{created.id}/documents")
            assert legacy.json()["total"] == 1
            assert (await client.get("/api/v1/document-types")).json()[
                "max_file_size_bytes"
            ] == settings.MAX_DOCUMENT_SIZE_BYTES
        async with sessions() as session:
            actions = list(await session.scalars(select(AuditLog.action)))
            for action in (
                "document.uploaded",
                "document.reviewed",
                "document.replaced",
                "document.downloaded",
                "document.deleted",
                "document_requirements.updated",
            ):
                assert action in actions
            assert (
                await session.scalar(select(func.count()).select_from(DocumentReview))
                == 2
            )


def test_upload_failures_roll_back_metadata_and_cleanup_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_PATH", tmp_path)
    asyncio.run(_upload_failures(tmp_path))


async def _upload_failures(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)
        storage = LocalDocumentStorage(root)
        # A foreign-key failure occurs after saving bytes but before commit.
        async with sessions() as session:
            with pytest.raises(IntegrityError):
                await upload_document(
                    session,
                    created.id,
                    DocumentType.PAN_CARD,
                    make_upload(),
                    User(id=uuid4()),
                    Request({"type": "http"}),
                    storage,
                )
        assert not list(root.rglob("*.pdf"))
        async with sessions() as session:
            session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
            with pytest.raises(RuntimeError, match="commit failed"):
                await upload_document(
                    session,
                    created.id,
                    DocumentType.PAN_CARD,
                    make_upload(),
                    actor,
                    Request({"type": "http"}),
                    storage,
                )
        assert not list(root.rglob("*.pdf"))
        async with sessions() as session:
            missing_id = uuid4()
            with pytest.raises(HTTPException) as error:
                await upload_document(
                    session,
                    missing_id,
                    DocumentType.PAN_CARD,
                    make_upload(),
                    actor,
                    Request({"type": "http"}),
                    storage,
                )
            assert error.value.status_code == 404
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Document)) == 0
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_concurrent_document_reviews_and_failed_review_are_atomic(tmp_path):
    asyncio.run(_concurrent_reviews(tmp_path))


async def _concurrent_reviews(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)
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

        async def review():
            async with sessions() as session:
                try:
                    return await verify_document(
                        session,
                        document.id,
                        DocumentVerification(expected_version=1, status="VERIFIED"),
                        actor,
                        Request({"type": "http"}),
                    )
                except HTTPException as error:
                    return error

        results = await asyncio.gather(review(), review())
        assert sum(isinstance(item, HTTPException) for item in results) == 1
        assert (
            next(
                item for item in results if isinstance(item, HTTPException)
            ).status_code
            == 409
        )
        async with sessions() as session:
            with pytest.raises(IntegrityError):
                await verify_document(
                    session,
                    document.id,
                    DocumentVerification(
                        expected_version=2, status="REJECTED", remarks="Bad copy"
                    ),
                    User(id=uuid4()),
                    Request({"type": "http"}),
                )
        async with sessions() as session:
            saved = await session.get(Document, document.id)
            assert saved.status == "VERIFIED" and saved.version == 2
            assert (
                await session.scalar(select(func.count()).select_from(DocumentReview))
                == 1
            )


def test_requirements_seed_is_idempotent_and_preserves_custom_configuration():
    asyncio.run(_seed_requirements())


async def _seed_requirements():
    async with (
        isolated_database() as (sessions, _actor, _payload),
        sessions() as session,
    ):
        await seed_initial_data(session)
        await session.commit()
        assert (
            await session.scalar(select(func.count()).select_from(DocumentRequirement))
            == 40
        )
        home = await session.scalar(
            select(LoanType).where(LoanType.name == "Home Loan")
        )
        property_requirement = await session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.loan_type_id == home.id,
                DocumentRequirement.document_type == "PROPERTY_DOCUMENTS",
            )
        )
        assert property_requirement.is_required
        property_requirement.is_required = False
        await session.commit()
        await seed_initial_data(session)
        await session.commit()
        await session.refresh(property_requirement)
        assert not property_requirement.is_required
        assert (
            await session.scalar(select(func.count()).select_from(DocumentRequirement))
            == 40
        )
        await session.execute(
            delete(DocumentRequirement).where(
                DocumentRequirement.loan_type_id == home.id
            )
        )
        await session.commit()
        await seed_initial_data(session)
        await session.commit()
        assert (
            await session.scalar(select(func.count()).select_from(DocumentRequirement))
            == 32
        )


def test_document_migration_backfills_existing_metadata():
    asyncio.run(_migration_roundtrip())


async def _migration_roundtrip():
    migration = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "b52f0a37d914_document_management.py"
        )
    )
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)
        document_id = uuid4()
        async with sessions() as session:
            connection = await session.connection()

            def downgrade(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration["downgrade"]()

            await connection.run_sync(downgrade)
            await session.execute(
                text("""
                INSERT INTO documents
                    (id, application_id, uploaded_by, document_type, original_filename, storage_key, mime_type, file_size)
                VALUES (:id, :application_id, :actor_id, 'legacy identity', 'original.pdf', 'original.pdf', 'application/pdf', 123)
            """),
                {"id": document_id, "application_id": created.id, "actor_id": actor.id},
            )

            def upgrade(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration["upgrade"]()

            await connection.run_sync(upgrade)
            await session.commit()
            saved = await session.get(Document, document_id)
            assert saved.document_group_id == document_id
            assert saved.status == "PENDING" and saved.version == saved.revision == 1
            assert saved.document_type == "legacy identity"
            assert saved.storage_key == "original.pdf"


def test_document_roles_and_missing_content(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_PATH", tmp_path)
    asyncio.run(_role_boundaries(tmp_path))


async def _role_boundaries(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)
        async with sessions() as session:
            await seed_initial_data(session)
            await session.commit()
            roles = {role.name: role.id for role in await session.scalars(select(Role))}
            users = {}
            for name in ("loan_officer", "underwriter", "customer"):
                user = User(
                    full_name=name,
                    email=f"{name}@example.com",
                    password_hash="unused",
                    role_id=roles[name],
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                users[name] = user
            await session.commit()
            document = await upload_document(
                session,
                created.id,
                DocumentType.PAN_CARD,
                make_upload(),
                actor,
                Request({"type": "http"}),
                LocalDocumentStorage(root),
            )

        async def override_get_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        path = f"/api/v1/documents/{document.id}"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            app.dependency_overrides[get_current_user] = lambda: users["customer"]
            for suffix in ("", "/download", "/reviews", "/revisions"):
                assert (await client.get(path + suffix)).status_code == 403
            for base in ("applications", "loan-applications"):
                result = await client.post(
                    f"/api/v1/{base}/{created.id}/documents",
                    data={"document_type": "PAN_CARD"},
                    files={"upload": ("pan.pdf", pdf_bytes(), "application/pdf")},
                )
                assert result.status_code == 403
            app.dependency_overrides[get_current_user] = lambda: users["loan_officer"]
            assert (await client.get(path + "/download")).status_code == 200
            officer_upload = await client.post(
                f"/api/v1/applications/{created.id}/documents",
                data={"document_type": "PHOTOGRAPH"},
                files={"upload": ("photo.pdf", pdf_bytes(), "application/pdf")},
            )
            assert officer_upload.status_code == 201, officer_upload.text
            assert (
                await client.patch(
                    path + "/verification",
                    json={
                        "expected_version": 1,
                        "status": "VERIFIED",
                    },
                )
            ).status_code == 403
            assert (
                await client.request(
                    "DELETE",
                    path,
                    json={
                        "expected_version": 1,
                        "remarks": "Not permitted",
                    },
                )
            ).status_code == 403
            assert (
                await client.put(
                    f"/api/v1/loan-types/{payload.loan_type_id}/document-requirements",
                    json={"requirements": []},
                )
            ).status_code == 403
            app.dependency_overrides[get_current_user] = lambda: users["underwriter"]
            assert (
                await client.post(
                    f"/api/v1/loan-applications/{created.id}/documents",
                    data={"document_type": "PAN_CARD"},
                    files={"upload": ("pan.pdf", pdf_bytes(), "application/pdf")},
                )
            ).status_code == 403
            reviewed = await client.patch(
                path + "/verification",
                json={
                    "expected_version": 1,
                    "status": "VERIFIED",
                },
            )
            assert reviewed.status_code == 200, reviewed.text
            assert (
                await client.request(
                    "DELETE",
                    path,
                    json={
                        "expected_version": 2,
                        "remarks": "Not permitted",
                    },
                )
            ).status_code == 403
            assert (
                await client.post(
                    path + "/replacement",
                    data={"document_type": "PAN_CARD", "expected_version": 2},
                    files={"upload": ("pan.pdf", pdf_bytes(), "application/pdf")},
                )
            ).status_code == 403
            app.dependency_overrides[get_current_user] = lambda: actor
            assert (
                await client.get(f"/api/v1/documents/{uuid4()}/download")
            ).status_code == 404
            for file in root.rglob("*.pdf"):
                file.unlink()
            assert (await client.get(path + "/download")).status_code == 404


def test_concurrent_replacements_and_rollback_preserve_original(tmp_path):
    asyncio.run(_concurrent_replacements(tmp_path))


async def _concurrent_replacements(root):
    async with isolated_database() as (sessions, actor, payload):
        created = await setup_documents(sessions, actor, payload)
        storage = LocalDocumentStorage(root)
        async with sessions() as session:
            original = await upload_document(
                session,
                created.id,
                DocumentType.PAN_CARD,
                make_upload(),
                actor,
                Request({"type": "http"}),
                storage,
            )
        async with sessions() as session:
            session.commit = AsyncMock(
                side_effect=RuntimeError("replacement commit failed")
            )
            with pytest.raises(RuntimeError, match="replacement commit failed"):
                await upload_document(
                    session,
                    created.id,
                    DocumentType.PAN_CARD,
                    make_upload(),
                    actor,
                    Request({"type": "http"}),
                    storage,
                    replaces_id=original.id,
                    expected_version=1,
                )
        assert len(list(root.rglob("*.pdf"))) == 1
        async with sessions() as session:
            previous = await session.get(Document, original.id)
            assert previous.replaced_at is None and previous.version == 1
            assert await session.scalar(select(func.count()).select_from(Document)) == 1

        async def replace():
            async with sessions() as session:
                try:
                    return await upload_document(
                        session,
                        created.id,
                        DocumentType.PAN_CARD,
                        make_upload(),
                        actor,
                        Request({"type": "http"}),
                        storage,
                        replaces_id=original.id,
                        expected_version=1,
                    )
                except HTTPException as error:
                    return error

        results = await asyncio.gather(replace(), replace())
        assert sum(isinstance(item, HTTPException) for item in results) == 1
        assert (
            next(
                item for item in results if isinstance(item, HTTPException)
            ).status_code
            == 409
        )
        assert len(list(root.rglob("*.pdf"))) == 2
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Document)) == 2
            previous = await session.get(Document, original.id)
            assert previous.version == 2 and previous.replaced_at is not None
