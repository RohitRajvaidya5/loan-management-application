import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models import LoginRateLimit


async def limit_login_attempts(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    peer = request.client.host if request.client else "unknown-peer"
    key = hmac.new(
        settings.JWT_SECRET_KEY.get_secret_value().encode(),
        peer.encode(),
        hashlib.sha256,
    ).hexdigest()
    now = datetime.now(UTC)
    reset = LoginRateLimit.window_start <= now - timedelta(minutes=1)
    statement = (
        insert(LoginRateLimit)
        .values(peer_digest=key, window_start=now, attempts=1)
        .on_conflict_do_update(
            index_elements=["peer_digest"],
            set_={
                "window_start": case((reset, now), else_=LoginRateLimit.window_start),
                "attempts": case((reset, 1), else_=LoginRateLimit.attempts + 1),
            },
        )
        .returning(LoginRateLimit.attempts)
    )
    try:
        attempts = await session.scalar(statement)
        await session.commit()
    finally:
        if session.in_transaction():
            await session.rollback()
    if attempts > settings.AUTH_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": "60"},
        )
