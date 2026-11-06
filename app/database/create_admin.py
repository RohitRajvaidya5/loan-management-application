import asyncio
from getpass import getpass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.database.session import AsyncSessionLocal, engine
from app.models import Role, User
from app.schemas.users import UserCreate


def prompt_for_admin(role_id: UUID) -> UserCreate:
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip()
    password = getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")

    return UserCreate(
        full_name=full_name,
        email=email,
        password=password,
        role_id=role_id,
    )


async def create_initial_admin(payload: UserCreate) -> None:
    async with AsyncSessionLocal() as session, session.begin():
        admin_role = await session.scalar(
            select(Role).where(Role.name == "administrator")
        )
        if admin_role is None:
            raise RuntimeError(
                "Administrator role not found. Run the database seeder first."
            )

        existing_admin_id = await session.scalar(
            select(User.id)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == "administrator")
            .limit(1)
        )
        if existing_admin_id is not None:
            raise RuntimeError(
                "An administrator already exists; use the protected user API."
            )

        if await session.scalar(
            select(User.id).where(User.email == str(payload.email))
        ):
            raise RuntimeError("A user with this email already exists.")

        session.add(
            User(
                full_name=payload.full_name,
                email=str(payload.email),
                password_hash=hash_password(payload.password.get_secret_value()),
                role_id=admin_role.id,
            )
        )
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            raise RuntimeError(
                "Could not create administrator; verify database data."
            ) from None


async def main() -> None:
    try:
        async with AsyncSessionLocal() as session:
            admin_role_id = await session.scalar(
                select(Role.id).where(Role.name == "administrator")
            )
        if admin_role_id is None:
            raise RuntimeError(
                "Administrator role not found. Run the database seeder first."
            )
        payload = prompt_for_admin(admin_role_id)
        await create_initial_admin(payload)
    finally:
        await engine.dispose()
    print("Initial administrator created. Sign in through POST /api/v1/auth/token.")


if __name__ == "__main__":
    asyncio.run(main())
