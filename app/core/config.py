from pathlib import Path
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    APP_NAME: str = "Loan Management API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: SecretStr
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, gt=0)
    DOCUMENT_STORAGE_PATH: Path = Path("var/documents")
    MAX_DOCUMENT_SIZE_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1, le=120)
    AUTH_RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, le=1000)
    NOTIFICATIONS_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=120)
    EMAIL_FROM: EmailStr = "no-reply@example.com"
    EMAIL_SENDER_NAME: str = Field(default="Loan Management", max_length=100)
    NOTIFICATION_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    NOTIFICATION_RETRY_SECONDS: int = Field(default=60, ge=1, le=86400)
    NOTIFICATION_LEASE_SECONDS: int = Field(default=300, ge=30, le=3600)

    @model_validator(mode="after")
    def production_safety(self):
        if self.APP_ENV not in ("development", "test", "production"):
            raise ValueError("APP_ENV must be development, test or production.")
        for origin in self.CORS_ORIGINS:
            parts = urlsplit(origin)
            if (
                parts.scheme not in ("https", "http")
                or not parts.hostname
                or parts.path
                or parts.query
                or parts.fragment
                or parts.username
                or parts.password
            ):
                raise ValueError(
                    "CORS origins must be explicit HTTP(S) origins without paths or credentials."
                )
        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            raise ValueError("SMTP username and password must be configured together.")
        if "\r" in self.EMAIL_SENDER_NAME or "\n" in self.EMAIL_SENDER_NAME:
            raise ValueError("Invalid email sender name.")
        if self.NOTIFICATION_LEASE_SECONDS <= self.SMTP_TIMEOUT_SECONDS:
            raise ValueError("Notification lease must exceed SMTP timeout.")
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled in production.")
            if not self.AUTH_RATE_LIMIT_ENABLED:
                raise ValueError(
                    "Login rate limiting must remain enabled in production."
                )
            secret = self.JWT_SECRET_KEY.get_secret_value().lower()
            if len(set(secret)) < 12 or any(
                word in secret
                for word in ("replace-with", "change-me", "unit-test-only")
            ):
                raise ValueError("Production requires a unique random JWT secret.")
            if any(not origin.startswith("https://") for origin in self.CORS_ORIGINS):
                raise ValueError("Production CORS origins must use HTTPS.")
            if self.NOTIFICATIONS_ENABLED and (
                not self.SMTP_STARTTLS or self.EMAIL_FROM.endswith("@example.com")
            ):
                raise ValueError(
                    "Production email requires TLS and a real sender address."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()


def get_async_database_url() -> str:
    database_url = make_url(settings.DATABASE_URL.get_secret_value())
    if database_url.drivername == "postgresql":
        database_url = database_url.set(drivername="postgresql+asyncpg")
    return database_url.render_as_string(hide_password=False)
