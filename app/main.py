from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.activity import router as activity_router
from app.api.v1.applications import router as applications_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.documents import router as documents_router
from app.api.v1.loan_applications import router as loan_applications_router
from app.api.v1.loan_types import router as loan_types_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.reports import router as reports_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.http import configure_http
from app.database.session import engine
from app.schemas.errors import ErrorResponse

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "development" else None,
    responses={
        code: {"model": ErrorResponse}
        for code in (401, 403, 404, 409, 422, 429, 500, 503)
    },
)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(customers_router, prefix="/api/v1/customers", tags=["Customers"])
app.include_router(
    applications_router, prefix="/api/v1/applications", tags=["Applications"]
)
app.include_router(
    loan_applications_router,
    prefix="/api/v1/loan-applications",
    tags=["Loan Applications"],
)
app.include_router(documents_router, prefix="/api/v1", tags=["Documents"])
app.include_router(audit_router, prefix="/api/v1/audit-logs", tags=["Audit Logs"])
app.include_router(activity_router, prefix="/api/v1", tags=["Application Activity"])
app.include_router(reports_router, prefix="/api/v1", tags=["Dashboard and Reports"])
app.include_router(
    notifications_router, prefix="/api/v1/notifications", tags=["Notifications"]
)
app.include_router(loan_types_router, prefix="/api/v1/loan-types", tags=["Loan Types"])
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
configure_http(app)


@app.get("/health/live", tags=["Health"])
def health_live():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "database": "connected",
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not ready",
                "database": "not connected",
            },
        )
