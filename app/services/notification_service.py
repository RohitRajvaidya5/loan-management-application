import logging
from hashlib import sha256
from uuid import UUID, uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Customer, LoanApplication, Notification, Role, User
from app.templates.emails import render_email

logger = logging.getLogger(__name__)
email_adapter = TypeAdapter(EmailStr)


async def enqueue_application_email(
    session: AsyncSession,
    application: LoanApplication,
    event: str,
    *,
    event_id: UUID | None = None,
    audience: str = "customer",
) -> None:
    if not settings.NOTIFICATIONS_ENABLED:
        return
    recipients: set[str] = set()
    if audience == "customer":
        email = await session.scalar(
            select(Customer.email).where(Customer.id == application.customer_id)
        )
        if email:
            recipients.add(email)
    elif audience == "assignee":
        if application.assigned_to:
            email = await session.scalar(
                select(User.email).where(
                    User.id == application.assigned_to, User.is_active.is_(True)
                )
            )
            if email:
                recipients.add(email)
    elif audience == "staff":
        recipients.update(
            await session.scalars(
                select(User.email)
                .join(Role, User.role_id == Role.id)
                .where(User.is_active.is_(True), Role.name == "administrator")
            )
        )
        if application.assigned_to:
            email = await session.scalar(
                select(User.email).where(
                    User.id == application.assigned_to, User.is_active.is_(True)
                )
            )
            if email:
                recipients.add(email)
    else:
        raise ValueError("Unknown notification audience.")
    if not recipients:
        logger.info("notification.skipped_missing_recipient event=%s", event)
        return
    subject, _, _ = render_email(event)
    for recipient in sorted(recipients):
        try:
            recipient = str(email_adapter.validate_python(recipient))
        except ValidationError:
            logger.warning("notification.skipped_invalid_recipient event=%s", event)
            continue
        recipient_key = sha256(recipient.encode()).hexdigest()
        key = f"{application.id}:{event_id or application.version}:{event}:{recipient_key}"
        await session.execute(
            insert(Notification)
            .values(
                id=uuid4(),
                application_id=application.id,
                recipient=recipient,
                event_type=event,
                subject=subject,
                template=event,
                event_key=key,
            )
            .on_conflict_do_nothing(index_elements=["event_key"])
        )
