import asyncio
import warnings
from io import BytesIO
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import settings

FORMATS = {
    "application/pdf": ({".pdf"}, b"%PDF-"),
    "image/jpeg": ({".jpg", ".jpeg"}, b"\xff\xd8\xff"),
    "image/png": ({".png"}, b"\x89PNG\r\n\x1a\n"),
}


def validate_content(content: bytes, mime_type: str) -> None:
    if not content.startswith(FORMATS[mime_type][1]):
        raise HTTPException(
            status_code=415, detail="File content does not match its format."
        )
    try:
        if mime_type == "application/pdf":
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError("Encrypted or empty PDF.")
            for page in reader.pages:
                page.get_contents()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if (
                        image.format
                        != {"image/jpeg": "JPEG", "image/png": "PNG"}[mime_type]
                    ):
                        raise ValueError("Image format mismatch.")
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    image.load()
    except (
        PdfReadError,
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(
            status_code=415,
            detail="Document is malformed, encrypted, or unsafe to parse.",
        ) from error


async def validate_upload(upload: UploadFile) -> tuple[str, str, str, bytes]:
    try:
        name = (upload.filename or "").replace("\\", "/")
        filename = PurePosixPath(name).name
        if (
            not filename
            or len(filename) > 255
            or any(ord(char) < 32 or ord(char) == 127 for char in filename)
        ):
            raise HTTPException(
                status_code=422,
                detail="A valid filename of at most 255 characters is required.",
            )
        mime_type = upload.content_type or ""
        if mime_type not in FORMATS:
            raise HTTPException(
                status_code=415,
                detail="Only PDF, JPEG, and PNG documents are supported.",
            )
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in FORMATS[mime_type][0]:
            raise HTTPException(
                status_code=415,
                detail="Filename extension does not match the declared media type.",
            )
        content = await upload.read(settings.MAX_DOCUMENT_SIZE_BYTES + 1)
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")
        if len(content) > settings.MAX_DOCUMENT_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Uploaded file is too large.")
        await asyncio.to_thread(validate_content, content, mime_type)
        return filename, mime_type, extension, content
    finally:
        await upload.close()
