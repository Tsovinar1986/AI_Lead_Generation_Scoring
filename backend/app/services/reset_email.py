"""Emails a password-reset link, via SendGrid if configured (better
deliverability/analytics at scale) or plain SMTP otherwise -- same
degrade-gracefully pattern as license_email.py. Kept as its own small
module rather than sharing code with it: the two send genuinely different
content, and the overlap is only ~30 lines.
"""

import smtplib
from email.message import EmailMessage

from loguru import logger

from ..config import (
    SENDGRID_API_KEY,
    SENDGRID_FROM_EMAIL,
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)

_BODY_TEMPLATE = (
    "We received a request to reset your password.\n\n"
    "Reset it here (expires in {ttl_minutes} minutes):\n{reset_url}\n\n"
    "If you didn't request this, you can safely ignore this email -- your "
    "password won't change unless you click the link above."
)


def _send_via_sendgrid(to_email: str, reset_url: str, ttl_minutes: int) -> bool:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject="Reset your password",
        plain_text_content=_BODY_TEMPLATE.format(reset_url=reset_url, ttl_minutes=ttl_minutes),
    )
    response = SendGridAPIClient(SENDGRID_API_KEY).send(message)
    if response.status_code >= 300:
        raise RuntimeError(f"SendGrid returned status {response.status_code}")
    return True


def _send_via_smtp(to_email: str, reset_url: str, ttl_minutes: int) -> bool:
    message = EmailMessage()
    message["Subject"] = "Reset your password"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(_BODY_TEMPLATE.format(reset_url=reset_url, ttl_minutes=ttl_minutes))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)
    return True


def send_password_reset_email(to_email: str, reset_url: str, ttl_minutes: int) -> bool:
    if SENDGRID_API_KEY and SENDGRID_FROM_EMAIL:
        try:
            _send_via_sendgrid(to_email, reset_url, ttl_minutes)
            logger.info("Password reset email sent to {} via SendGrid", to_email)
            return True
        except Exception as exc:  # noqa: BLE001 - never let email failure break the request
            logger.warning("SendGrid send failed for {}: {}", to_email, exc)
            return False

    if SMTP_HOST and SMTP_FROM_EMAIL:
        try:
            _send_via_smtp(to_email, reset_url, ttl_minutes)
            logger.info("Password reset email sent to {} via SMTP", to_email)
            return True
        except Exception as exc:  # noqa: BLE001 - never let email failure break the request
            logger.warning("SMTP send failed for {}: {}", to_email, exc)
            return False

    logger.info("No email provider configured — password reset for {} not emailed.", to_email)
    return False
