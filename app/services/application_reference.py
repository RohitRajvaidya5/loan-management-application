from datetime import UTC, datetime

from sqlalchemy import Sequence, select
from sqlalchemy.ext.asyncio import AsyncSession

reference_sequence = Sequence("loan_application_reference_seq")


async def generate_reference(session: AsyncSession) -> str:
    number = (
        await session.execute(select(reference_sequence.next_value()))
    ).scalar_one()
    return f"LN-{datetime.now(UTC).year}-{number:06d}"
