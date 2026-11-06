import argparse
import asyncio
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from app.core.config import settings
from app.database.session import AsyncSessionLocal, engine
from app.models import Notification
from app.services.email_service import EmailSender, SMTPEmailSender

logger = logging.getLogger(__name__)


async def process_one(sessions, sender: EmailSender) -> bool:
    if not settings.NOTIFICATIONS_ENABLED:
        raise RuntimeError(
            "Set NOTIFICATIONS_ENABLED=true before starting the notification worker."
        )
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        # A crash during the final attempt must not leave a job permanently PROCESSING.
        await session.execute(
            update(Notification)
            .where(
                Notification.status == "PROCESSING",
                Notification.lease_until < now,
                Notification.retry_count >= settings.NOTIFICATION_MAX_ATTEMPTS,
            )
            .values(
                status="FAILED",
                lease_until=None,
                lease_token=None,
                last_error="LeaseExpired",
            )
        )
        row = await session.scalar(
            select(Notification)
            .where(
                Notification.retry_count < settings.NOTIFICATION_MAX_ATTEMPTS,
                or_(
                    and_(
                        Notification.status.in_(("PENDING", "FAILED")),
                        Notification.available_at <= now,
                    ),
                    and_(
                        Notification.status == "PROCESSING",
                        Notification.lease_until < now,
                    ),
                ),
            )
            .order_by(Notification.available_at, Notification.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        row.status = "PROCESSING"
        row.retry_count += 1
        row.lease_until = now + timedelta(seconds=settings.NOTIFICATION_LEASE_SECONDS)
        row.lease_token = uuid4()
        identifier, recipient, template = row.id, row.recipient, row.template
        lease_token, attempts = row.lease_token, row.retry_count
    try:
        reference = await asyncio.to_thread(
            sender.send, identifier, recipient, template
        )
    except (smtplib.SMTPException, OSError, TimeoutError) as error:
        # Provider exception text can contain recipient addresses or credentials.
        error_code = type(error).__name__
        logger.warning(
            "notification.delivery_failed id=%s error_type=%s", identifier, error_code
        )
        values = {
            "status": "FAILED",
            "last_error": error_code,
            "available_at": datetime.now(UTC)
            + timedelta(
                seconds=settings.NOTIFICATION_RETRY_SECONDS * 2 ** (attempts - 1)
            ),
            "lease_until": None,
            "lease_token": None,
        }
    else:
        values = {
            "status": "SENT",
            "sent_at": datetime.now(UTC),
            "provider_reference": reference[:255],
            "last_error": None,
            "lease_until": None,
            "lease_token": None,
        }
    async with sessions() as session, session.begin():
        await session.execute(
            update(Notification)
            .where(
                Notification.id == identifier,
                Notification.lease_token == lease_token,
            )
            .values(**values)
        )
    return True


async def run_worker(once: bool, limit: int) -> None:
    try:
        processed = 0
        while True:
            found = await process_one(AsyncSessionLocal, SMTPEmailSender())
            if found:
                processed += 1
            if once and (not found or processed >= limit):
                return
            if not found:
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable email outbox jobs.")
    parser.add_argument(
        "--once", action="store_true", help="Drain at most --limit due jobs and exit."
    )
    parser.add_argument("--limit", type=int, default=100)
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be positive")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run_worker(arguments.once, arguments.limit))


if __name__ == "__main__":
    main()
