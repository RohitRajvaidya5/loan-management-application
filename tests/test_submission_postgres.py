import asyncio
import os

import pytest
from sqlalchemy import func, select
from starlette.requests import Request
from test_phase4_postgres import isolated_database

from app.models import ApplicationStatusHistory, AuditLog, LoanApplication
from app.services.loan_application_service import submit_application

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 with a dedicated TEST_DATABASE_URL.",
)


def test_submission_persists_application_history_and_audit_in_postgres():
    asyncio.run(_verify_submission())


async def _verify_submission():
    async with isolated_database() as (sessions, actor, payload):
        async with sessions() as session:
            created = await submit_application(
                session, payload, actor, Request({"type": "http"})
            )
        async with sessions() as session:
            assert await session.get(LoanApplication, created.id) is not None
            assert (
                await session.scalar(
                    select(func.count()).select_from(ApplicationStatusHistory)
                )
                == 1
            )
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1
