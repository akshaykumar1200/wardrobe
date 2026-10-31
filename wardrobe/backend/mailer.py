import logging
import smtplib
from email.message import EmailMessage

from backend.config import settings

logger = logging.getLogger(__name__)


def send_reset_email(to_email: str, reset_url: str) -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("Password reset email not sent: SMTP_USER or SMTP_PASSWORD is not configured")
        return

    message = EmailMessage()
    message["Subject"] = "Reset your wardrobe password"
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to_email
    message.set_content(
        f"Use this link to reset your password:\n\n{reset_url}\n\n"
        f"This link expires in {settings.RESET_TOKEN_MINUTES} minutes and can be used once."
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.error("Failed to send password reset email to %s", to_email)
