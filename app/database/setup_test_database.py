"""Explicit local-development helper; never alters an existing database."""

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main() -> None:
    source = make_url(settings.DATABASE_URL.get_secret_value())
    target_name = "loan_management_test"
    if source.database == target_name or settings.APP_ENV != "development":
        raise RuntimeError(
            "Run this only from a development application database configuration."
        )
    admin = source.set(drivername="postgresql+asyncpg", database="postgres")
    engine = create_async_engine(admin, isolation_level="AUTOCOMMIT", echo=False)
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_name},
            )
            if not exists:
                await connection.execute(text('CREATE DATABASE "loan_management_test"'))
    finally:
        await engine.dispose()
    target = source.set(database=target_name).render_as_string(hide_password=False)
    await asyncio.to_thread(write_test_config, target)
    print(
        "Dedicated test database available; .env.test is configured. No credentials printed."
    )


def write_test_config(target: str) -> None:
    path = Path(".env.test")
    # Never overwrite a user's existing test configuration.
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(f"TEST_DATABASE_URL='{target}'\n")


if __name__ == "__main__":
    asyncio.run(main())
