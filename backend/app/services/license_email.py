"""Emails an issued license key to the buyer via SMTP.

Same degrade-gracefully pattern as every other integration in this app:
without SMTP_HOST/SMTP_FROM_EMAIL configured, this just logs and returns
False so the caller (routers/billing.py) knows to rely on
licensing/issued_licenses.jsonl instead.
"""

import smtplib
from email.message import EmailMessage

from loguru import logger

from ..config import SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME


def send_license_email(to_email: str, license_key: str, plan: str) -> bool:
    if not (SMTP_HOST and SMTP_FROM_EMAIL):
        logger.info("SMTP not configured — license for {} logged only, not emailed.", to_email)
        return False

    message = EmailMessage()
    message["Subject"] = "Your license key"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(
        "Thanks for your purchase!\n\n"
        f"Plan: {plan}\n"
        f"License key:\n{license_key}\n\n"
        "Add it to your .env as LICENSE_KEY (and set LICENSE_REQUIRED=true) "
        "to unlock the full product. If you're on a subscription, a fresh "
        "key is issued automatically each billing cycle -- no action needed "
        "as long as payment keeps succeeding."
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("License email sent to {}", to_email)
        return True
    except Exception as exc:  # noqa: BLE001 - never let email failure break license issuance
        logger.warning("Failed to email license to {}: {}", to_email, exc)
        return False
