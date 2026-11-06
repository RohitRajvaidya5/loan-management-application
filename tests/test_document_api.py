import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.database.session import get_db
from app.enums.document import DocumentType
from app.main import app
from app.models import Document
from app.schemas.documents import (
    DocumentDeletion,
    DocumentVerification,
    RequirementsUpdate,
)
from app.services.file_validation import validate_upload
from app.services.storage_service import LocalDocumentStorage, get_document_storage


def pdf_bytes() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    return stream.getvalue()


def image_bytes(format: str) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (4, 4), "white").save(stream, format=format)
    return stream.getvalue()


def make_upload(name="pan.pdf", content=None, mime="application/pdf") -> UploadFile:
    return UploadFile(
        BytesIO(pdf_bytes() if content is None else content),
        filename=name,
        headers=Headers({"content-type": mime}),
    )


@pytest.fixture
def document_context(tmp_path, monkeypatch):
    application_id = uuid4()
    actor = SimpleNamespace(id=uuid4(), role_id=uuid4())
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=uuid4())
    )
    session.get.return_value = SimpleNamespace(id=application_id)
    added = []
    session.add.side_effect = added.append

    async def flush():
        for item in added:
            if isinstance(item, Document):
                item.uploaded_at = datetime.now(UTC)

    session.flush.side_effect = flush

    async def scalar(statement):
        return next((item for item in added if isinstance(item, Document)), None)

    session.scalar.side_effect = scalar

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: actor
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_PATH", tmp_path)
    try:
        with TestClient(app) as client:
            yield client, session, application_id, added, tmp_path
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("base", ["applications", "loan-applications"])
def test_document_upload_stores_file_and_returns_safe_metadata(document_context, base):
    client, _session, application_id, _added, root = document_context
    content = pdf_bytes()
    response = client.post(
        f"/api/v1/{base}/{application_id}/documents",
        data={"document_type": "PAN_CARD"},
        files={"upload": ("../../identity.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    metadata = response.json()
    assert metadata["application_id"] == str(application_id)
    assert metadata["original_filename"] == "identity.pdf"
    assert metadata["status"] == "PENDING"
    assert metadata["revision"] == metadata["version"] == 1
    assert metadata["file_size"] == len(content)
    assert "storage_key" not in metadata
    stored_files = list(root.rglob("*.pdf"))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == content
    for suffix in ("download", "content"):
        downloaded = client.get(f"/api/v1/documents/{metadata['id']}/{suffix}")
        assert downloaded.status_code == 200
        assert downloaded.content == content
        assert downloaded.headers["cache-control"] == "no-store"
        assert downloaded.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("name", "mime", "content", "status"),
    [
        ("bad.exe", "application/octet-stream", b"exe", 415),
        ("bad.exe", "application/pdf", b"%PDF-1.7\n", 415),
        ("bad.pdf", "image/png", b"\x89PNG\r\n\x1a\n", 415),
        ("bad.pdf", "application/pdf", b"%PDF-1.7\nfake", 415),
        ("bad.png", "image/png", b"\x89PNG\r\n\x1a\nfake", 415),
        ("bad.jpg", "image/jpeg", b"\xff\xd8\xfffake", 415),
        ("empty.pdf", "application/pdf", b"", 422),
        ("", "application/pdf", b"content", 422),
        ("bad\r\n.pdf", "application/pdf", b"content", 422),
        ("a" * 256 + ".pdf", "application/pdf", b"content", 422),
    ],
)
def test_invalid_files_are_rejected_and_closed(name, mime, content, status):
    upload = make_upload(name, content, mime)
    with pytest.raises(HTTPException) as error:
        asyncio.run(validate_upload(upload))
    assert error.value.status_code == status
    assert upload.file.closed


@pytest.mark.parametrize(
    ("name", "mime", "content"),
    [
        ("pan.PDF", "application/pdf", pdf_bytes()),
        ("photo.jpeg", "image/jpeg", image_bytes("JPEG")),
        ("photo.jpg", "image/jpeg", image_bytes("JPEG")),
        ("photo.png", "image/png", image_bytes("PNG")),
    ],
)
def test_valid_formats_are_parsed(name, mime, content):
    upload = make_upload(name, content, mime)
    filename, detected, _extension, result = asyncio.run(validate_upload(upload))
    assert filename == name and detected == mime and result == content
    assert upload.file.closed


def test_encrypted_pdf_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(HTTPException) as error:
        asyncio.run(validate_upload(make_upload(content=stream.getvalue())))
    assert error.value.status_code == 415


def test_file_size_boundary(monkeypatch):
    content = pdf_bytes()
    monkeypatch.setattr(settings, "MAX_DOCUMENT_SIZE_BYTES", len(content))
    assert asyncio.run(validate_upload(make_upload(content=content)))[3] == content
    with pytest.raises(HTTPException) as error:
        asyncio.run(validate_upload(make_upload(content=content + b"x")))
    assert error.value.status_code == 413


@pytest.mark.parametrize(
    "key",
    ["../secret", "/secret", "C:\\secret", "a\\..\\secret", "a/../secret", "", "a//b"],
)
def test_storage_prevents_path_traversal(tmp_path, key):
    with pytest.raises(HTTPException) as error:
        LocalDocumentStorage(tmp_path).path(key)
    assert error.value.status_code == 404


def test_storage_unique_names_and_missing_content(tmp_path):
    async def run():
        storage = LocalDocumentStorage(tmp_path)
        first = await storage.save(str(uuid4()), ".pdf", b"first")
        second = await storage.save(str(uuid4()), ".pdf", b"second")
        assert first != second
        stream = await storage.open(first)
        assert stream.read() == b"first"
        stream.close()
        await storage.delete(first)
        with pytest.raises(HTTPException) as error:
            await storage.open(first)
        assert error.value.status_code == 404

    asyncio.run(run())


def test_storage_write_and_cleanup_failures_are_explicit(tmp_path, monkeypatch, caplog):
    storage = LocalDocumentStorage(tmp_path)

    def fail_open(*args, **kwargs):
        raise PermissionError("test storage unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", fail_open)
        with pytest.raises(HTTPException) as error:
            asyncio.run(storage.save(str(uuid4()), ".pdf", b"pdf"))
        assert error.value.status_code == 503
        with pytest.raises(HTTPException) as error:
            asyncio.run(storage.open("file.pdf"))
        assert error.value.status_code == 503
    with monkeypatch.context() as patch:
        patch.setattr(
            Path, "unlink", Mock(side_effect=PermissionError("cleanup failed"))
        )
        with pytest.raises(HTTPException) as error:
            asyncio.run(storage.delete("file.pdf"))
        assert error.value.status_code == 503
    assert "storage write failed" in caplog.text
    assert "rollback cleanup failed" in caplog.text


def test_partial_storage_write_is_cleaned_up(tmp_path, monkeypatch):
    original_open = Path.open

    class BrokenWriter:
        def __init__(self, path):
            self.stream = original_open(path, "xb")

        def __enter__(self):
            return self

        def write(self, content):
            self.stream.write(content[:1])
            raise OSError("disk full")

        def __exit__(self, *args):
            self.stream.close()

    def open_file(path, mode):
        assert mode == "xb"
        return BrokenWriter(path)

    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            LocalDocumentStorage(tmp_path).save(str(uuid4()), ".pdf", b"content")
        )
    assert error.value.status_code == 503
    assert not list(tmp_path.rglob("*.pdf"))


def test_cancelled_storage_write_is_cleaned_up(tmp_path, monkeypatch):
    original_open = Path.open
    started, release = Event(), Event()

    class SlowWriter:
        def __init__(self, path):
            self.stream = original_open(path, "xb")

        def __enter__(self):
            return self

        def write(self, content):
            started.set()
            assert release.wait(timeout=5)
            return self.stream.write(content)

        def __exit__(self, *args):
            self.stream.close()

    monkeypatch.setattr(Path, "open", lambda path, mode: SlowWriter(path))

    async def cancel_write():
        task = asyncio.create_task(
            LocalDocumentStorage(tmp_path).save(str(uuid4()), ".pdf", b"pdf")
        )
        try:
            assert await asyncio.to_thread(started.wait, 5)
            task.cancel()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_write())
    assert not list(tmp_path.rglob("*.pdf"))


def test_unauthenticated_document_download_is_denied():
    with TestClient(app) as client:
        assert client.get(f"/api/v1/documents/{uuid4()}/download").status_code == 401


def test_download_audit_failure_closes_stream_and_rolls_back(
    document_context, monkeypatch
):
    client, session, application_id, _added, root = document_context
    response = client.post(
        f"/api/v1/loan-applications/{application_id}/documents",
        data={"document_type": "PAN_CARD"},
        files={"upload": ("pan.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 201
    storage = LocalDocumentStorage(root)
    original_open = storage.open
    streams = []

    async def open_stream(key):
        stream = await original_open(key)
        streams.append(stream)
        return stream

    monkeypatch.setattr(storage, "open", open_stream)
    app.dependency_overrides[get_document_storage] = lambda: storage
    session.commit.side_effect = RuntimeError("audit commit failed")
    try:
        failed = client.get(f"/api/v1/documents/{response.json()['id']}/download")
        assert failed.status_code == 500
        assert failed.json()["code"] == "INTERNAL_ERROR"
        assert "audit commit failed" not in failed.text
        assert len(streams) == 1 and streams[0].closed
        session.rollback.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_document_storage, None)


@pytest.mark.parametrize("base", ["applications", "loan-applications"])
def test_upload_requires_permission_and_valid_category(document_context, base):
    client, session, application_id, added, root = document_context
    path = f"/api/v1/{base}/{application_id}/documents"
    invalid = client.post(
        path,
        data={"document_type": "identity"},
        files={
            "upload": ("pan.pdf", pdf_bytes(), "application/pdf"),
        },
    )
    assert invalid.status_code == 422
    session.execute.return_value.scalar_one_or_none.return_value = None
    denied = client.post(
        path,
        data={"document_type": "PAN_CARD"},
        files={
            "upload": ("pan.pdf", pdf_bytes(), "application/pdf"),
        },
    )
    assert denied.status_code == 403
    assert not added and not list(root.rglob("*"))


@pytest.mark.parametrize("status", ["REJECTED", "RESUBMISSION_REQUIRED"])
def test_negative_review_requires_nonblank_remarks(status):
    for remarks in (None, "", "   "):
        with pytest.raises(ValueError):
            DocumentVerification(expected_version=1, status=status, remarks=remarks)


def test_review_and_configuration_schema_rules():
    with pytest.raises(ValueError):
        DocumentVerification(expected_version=1, status="PENDING")
    with pytest.raises(ValueError):
        DocumentDeletion(expected_version=1, remarks="   ")
    with pytest.raises(ValueError):
        RequirementsUpdate(
            requirements=[
                {"document_type": "PAN_CARD", "is_required": True},
                {"document_type": "PAN_CARD", "is_required": False},
            ]
        )
    with pytest.raises(ValueError):
        RequirementsUpdate(
            requirements=[{"document_type": "identity", "is_required": True}]
        )
    assert len(DocumentType) == 8


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/document-types", None),
        ("GET", f"/api/v1/documents/{uuid4()}", None),
        ("GET", f"/api/v1/documents/{uuid4()}/download", None),
        ("GET", f"/api/v1/documents/{uuid4()}/content", None),
        ("GET", f"/api/v1/documents/{uuid4()}/reviews", None),
        ("GET", f"/api/v1/documents/{uuid4()}/revisions", None),
        (
            "PATCH",
            f"/api/v1/documents/{uuid4()}/verification",
            {"status": "VERIFIED", "expected_version": 1},
        ),
        (
            "DELETE",
            f"/api/v1/documents/{uuid4()}",
            {"expected_version": 1, "remarks": "duplicate"},
        ),
        (
            "PUT",
            f"/api/v1/loan-types/{uuid4()}/document-requirements",
            {"requirements": []},
        ),
    ],
)
def test_document_routes_deny_unprivileged_users(
    document_context, method, path, payload
):
    client, session, _, added, root = document_context
    session.execute.return_value.scalar_one_or_none.return_value = None
    response = client.request(method, path, json=payload)
    assert response.status_code == 403
    session.commit.assert_not_awaited()
    assert not added and not list(root.rglob("*"))
