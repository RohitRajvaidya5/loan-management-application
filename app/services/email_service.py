import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol
from uuid import UUID

from app.core.config import settings
from app.templates.emails import render_email


class EmailSender(Protocol):
    def send(self, identifier: UUID, recipient: str, template: str) -> str: ...


class SMTPEmailSender:
    def send(self, identifier: UUID, recipient: str, template: str) -> str:
        if not settings.NOTIFICATIONS_ENABLED:
            raise RuntimeError("Email delivery is disabled.")
        subject, text, html = render_email(template)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr(
            (settings.EMAIL_SENDER_NAME, str(settings.EMAIL_FROM))
        )
        message["To"] = recipient
        message["Message-ID"] = (
            f"<{identifier}@{str(settings.EMAIL_FROM).split('@')[1]}>"
        )
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                smtp.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD.get_secret_value()
                    if settings.SMTP_PASSWORD
                    else "",
                )
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
        return str(message["Message-ID"])
