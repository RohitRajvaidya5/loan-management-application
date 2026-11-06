import asyncio
import logging
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentStorage(Protocol):
    async def save(
        self, application_id: str, extension: str, content: bytes
    ) -> str: ...
    async def delete(self, key: str) -> None: ...
    async def open(self, key: str) -> BinaryIO: ...


class LocalDocumentStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        parts = PurePosixPath(key)
        if (
            not key
            or "\\" in key
            or ":" in key
            or parts.is_absolute()
            or any(part in ("", ".", "..") for part in key.split("/"))
        ):
            raise HTTPException(status_code=404, detail="Document content not found.")
        path = self.root.joinpath(*parts.parts).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise HTTPException(status_code=404, detail="Document content not found.")
        return path

    async def save(self, application_id: str, extension: str, content: bytes) -> str:
        key = f"{application_id}/{uuid4().hex}{extension}"
        path = self.path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            created = False
            completed = False
            try:
                with path.open("xb") as stream:
                    created = True
                    stream.write(content)
                completed = True
            finally:
                if created and not completed:
                    path.unlink()

        try:
            write_task = asyncio.create_task(asyncio.to_thread(write))
            try:
                await asyncio.shield(write_task)
            except asyncio.CancelledError:
                await write_task
                await self.delete(key)
                raise
        except OSError as error:
            logger.exception("Document storage write failed.")
            raise HTTPException(
                status_code=503, detail="Document storage unavailable."
            ) from error
        return key

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self.path(key).unlink, missing_ok=True)
        except OSError as error:
            logger.exception("Document upload rollback cleanup failed for key %s.", key)
            raise HTTPException(
                status_code=503,
                detail="Document cleanup failed; operator action required.",
            ) from error

    async def open(self, key: str) -> BinaryIO:
        try:
            return await asyncio.to_thread(self.path(key).open, "rb")
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Document content not found."
            ) from error
        except OSError as error:
            logger.exception("Document storage read failed.")
            raise HTTPException(
                status_code=503, detail="Document storage unavailable."
            ) from error


def get_document_storage() -> DocumentStorage:
    return LocalDocumentStorage(settings.DOCUMENT_STORAGE_PATH)
