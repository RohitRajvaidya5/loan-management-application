import json
import logging
import time
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

logger = logging.getLogger("loan_api")


def error_response(request: Request, status: int, code: str, detail, headers=None):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status,
        content={"detail": detail, "code": code, "request_id": request_id},
        headers={
            **(headers or {}),
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
        },
    )


def configure_http(app: FastAPI) -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        try:
            request_id = str(UUID(supplied))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:  # noqa: BLE001 - safe logged boundary; never log exception text
            response = await unexpected_error(request, error)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "route": getattr(route, "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return error_response(
            request,
            error.status_code,
            f"HTTP_{error.status_code}",
            error.detail,
            error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        details = [
            {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return error_response(request, 422, "VALIDATION_ERROR", details)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        logger.error(
            json.dumps(
                {
                    "event": "database_error",
                    "request_id": request.state.request_id,
                    "error_type": type(error).__name__,
                }
            )
        )
        if isinstance(error, IntegrityError):
            return error_response(
                request,
                409,
                "DATA_CONFLICT",
                "The operation conflicts with related or existing data.",
            )
        return error_response(
            request,
            503,
            "DATABASE_UNAVAILABLE",
            "The database operation could not be completed.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logger.error(
            json.dumps(
                {
                    "event": "internal_error",
                    "request_id": getattr(request.state, "request_id", None),
                    "error_type": type(error).__name__,
                }
            )
        )
        return error_response(
            request, 500, "INTERNAL_ERROR", "An unexpected error occurred."
        )
