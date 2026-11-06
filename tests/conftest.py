import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("NOTIFICATIONS_ENABLED", "false")

if os.environ.get("RUN_POSTGRES_INTEGRATION") == "1":
    configured = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    test_config = dotenv_values(Path(__file__).resolve().parents[1] / ".env.test")
    test_url = os.environ.get("TEST_DATABASE_URL") or test_config.get(
        "TEST_DATABASE_URL"
    )
    app_url = os.environ.get("DATABASE_URL") or configured.get("DATABASE_URL")
    if (os.environ.get("APP_ENV") or configured.get("APP_ENV")) == "production":
        raise pytest.UsageError("Integration tests refuse a production environment.")
    if not test_url:
        raise pytest.UsageError(
            "PostgreSQL tests require TEST_DATABASE_URL or .env.test. Run uv run python -m app.database.setup_test_database."
        )
    parsed = make_url(test_url)
    if not parsed.database or not parsed.database.endswith("_test"):
        raise pytest.UsageError(
            "TEST_DATABASE_URL must use a dedicated database ending in _test."
        )
    if app_url and parsed.database == make_url(app_url).database:
        raise pytest.UsageError(
            "Integration tests must not use the application database."
        )
    os.environ["DATABASE_URL"] = test_url
else:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost/loan_management_test",
    )
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "unit-test-only-secret-key-that-is-at-least-32-characters",
)
