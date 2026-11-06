from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.schemas.auth import LoginRequest


async def authenticate_user(
    session: AsyncSession, credentials: LoginRequest
) -> User | None:
    result = await session.execute(
        select(User).where(User.email == credentials.email).with_for_update(of=User)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None

    password_is_valid = verify_password(
        credentials.password.get_secret_value(),
        user.password_hash,
    )
    if not password_is_valid or not user.is_active:
        return None

    return user
