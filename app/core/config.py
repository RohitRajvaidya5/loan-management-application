from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    APP_NAME: str = "Loan Management API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: SecretStr

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()


def get_async_database_url() -> str:
    database_url = make_url(settings.DATABASE_URL.get_secret_value())
    if database_url.drivername == "postgresql":
        database_url = database_url.set(drivername="postgresql+asyncpg")
    return database_url.render_as_string(hide_password=False)
