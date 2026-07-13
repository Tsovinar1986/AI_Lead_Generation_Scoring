"""Emails an issued license key to the buyer, via SendGrid if configured
(better deliverability/analytics at scale) or plain SMTP otherwise.

Same degrade-gracefully pattern as every other integration in this app:
without SENDGRID_API_KEY or SMTP_HOST configured, this just logs and returns
False so the caller (routers/billing.py) knows to rely on
licensing/issued_licenses.jsonl instead.
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
    "Thanks for your purchase!\n\n"
    "Plan: {plan}\n"
    "License key:\n{license_key}\n\n"
    "Add it to your .env as LICENSE_KEY (and set LICENSE_REQUIRED=true) "
    "to unlock the full product. If you're on a subscription, a fresh "
    "key is issued automatically each billing cycle -- no action needed "
    "as long as payment keeps succeeding."
)


def _send_via_sendgrid(to_email: str, license_key: str, plan: str) -> bool:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject="Your license key",
        plain_text_content=_BODY_TEMPLATE.format(plan=plan, license_key=license_key),
    )
    response = SendGridAPIClient(SENDGRID_API_KEY).send(message)
    if response.status_code >= 300:
        raise RuntimeError(f"SendGrid returned status {response.status_code}")
    return True


def _send_via_smtp(to_email: str, license_key: str, plan: str) -> bool:
    message = EmailMessage()
    message["Subject"] = "Your license key"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(_BODY_TEMPLATE.format(plan=plan, license_key=license_key))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)
    return True


def send_license_email(to_email: str, license_key: str, plan: str) -> bool:
    if SENDGRID_API_KEY and SENDGRID_FROM_EMAIL:
        try:
            _send_via_sendgrid(to_email, license_key, plan)
            logger.info("License email sent to {} via SendGrid", to_email)
            return True
        except Exception as exc:  # noqa: BLE001 - never let email failure break license issuance
            logger.warning("SendGrid send failed for {}: {}", to_email, exc)
            return False

    if SMTP_HOST and SMTP_FROM_EMAIL:
        try:
            _send_via_smtp(to_email, license_key, plan)
            logger.info("License email sent to {} via SMTP", to_email)
            return True
        except Exception as exc:  # noqa: BLE001 - never let email failure break license issuance
            logger.warning("SMTP send failed for {}: {}", to_email, exc)
            return False

    logger.info("No email provider configured — license for {} logged only, not emailed.", to_email)
    return False
