"""PayPal checkout and license delivery for the seller storefront."""

import json
import sys
import time
from pathlib import Path
from typing import Literal

import requests
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from ..config import (
    APP_BASE_URL,
    LICENSE_PRIVATE_KEY,
    LICENSE_VALIDITY_DAYS_ANNUAL,
    LICENSE_VALIDITY_DAYS_MONTHLY,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_CURRENCY,
    PAYPAL_ENVIRONMENT,
    PAYPAL_PRICE_ADVANCED_ANNUAL,
    PAYPAL_PRICE_ADVANCED_MONTHLY,
    PAYPAL_PRICE_ANNUAL,
    PAYPAL_PRICE_MONTHLY,
)
from ..services.license_email import send_license_email

_LICENSING_DIR = Path(__file__).resolve().parents[3] / "licensing"
sys.path.insert(0, str(_LICENSING_DIR))
from issue_license import issue_license  # noqa: E402

router = APIRouter(prefix="/api/billing", tags=["billing"])
_ISSUED_LICENSES_LOG = _LICENSING_DIR / "issued_licenses.jsonl"


def _paypal_api_base() -> str:
    return "https://api-m.sandbox.paypal.com" if PAYPAL_ENVIRONMENT == "sandbox" else "https://api-m.paypal.com"


def _paypal_access_token() -> str:
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="PayPal isn't configured on this deployment.")
    response = requests.post(
        f"{_paypal_api_base()}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json"},
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    if not response.ok:
        logger.warning("Couldn't obtain PayPal access token: {} {}", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Couldn't connect to PayPal.")
    return response.json()["access_token"]


def _price_for(tier: str, interval: str) -> str:
    if tier == "advanced":
        return PAYPAL_PRICE_ADVANCED_ANNUAL if interval == "annual" else PAYPAL_PRICE_ADVANCED_MONTHLY
    return PAYPAL_PRICE_ANNUAL if interval == "annual" else PAYPAL_PRICE_MONTHLY


def _validity_days(interval: str) -> int:
    return LICENSE_VALIDITY_DAYS_ANNUAL if interval == "annual" else LICENSE_VALIDITY_DAYS_MONTHLY


def _already_issued(order_id: str) -> bool:
    if not _ISSUED_LICENSES_LOG.exists():
        return False
    with _ISSUED_LICENSES_LOG.open() as log:
        for line in log:
            try:
                if json.loads(line).get("transaction_id") == order_id:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def _issue_and_deliver(email: str, interval: str, tier: str, order_id: str) -> str:
    if not LICENSE_PRIVATE_KEY:
        logger.error("Payment received for {} but LICENSE_PRIVATE_KEY isn't set.", email)
        raise HTTPException(status_code=500, detail="License signing key not configured on this deployment.")

    license_key = issue_license(
        email,
        plan=interval,
        private_key_b64=LICENSE_PRIVATE_KEY,
        days=_validity_days(interval),
        tier=tier,
    )
    _ISSUED_LICENSES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _ISSUED_LICENSES_LOG.open("a") as log:
        log.write(
            json.dumps(
                {
                    "email": email,
                    "license_key": license_key,
                    "issued_at": time.time(),
                    "transaction_id": order_id,
                }
            )
            + "\n"
        )
    emailed = send_license_email(email, license_key, interval)
    logger.info(
        "Issued license for {} ({}){}",
        email,
        interval,
        "" if emailed else " — not emailed, see licensing/issued_licenses.jsonl",
    )
    return license_key


class PayPalCheckoutRequest(BaseModel):
    interval: Literal["monthly", "annual"]
    tier: Literal["pro", "advanced"] = "pro"


class PayPalCaptureRequest(BaseModel):
    order_id: str


@router.get("/config")
def billing_config():
    return {
        "paypal_available": bool(
            PAYPAL_CLIENT_ID
            and PAYPAL_CLIENT_SECRET
            and PAYPAL_PRICE_MONTHLY
            and PAYPAL_PRICE_ANNUAL
            and PAYPAL_PRICE_ADVANCED_MONTHLY
            and PAYPAL_PRICE_ADVANCED_ANNUAL
        ),
        "currency": PAYPAL_CURRENCY,
        "environment": PAYPAL_ENVIRONMENT,
        "price_monthly": PAYPAL_PRICE_MONTHLY or None,
        "price_annual": PAYPAL_PRICE_ANNUAL or None,
        "price_advanced_monthly": PAYPAL_PRICE_ADVANCED_MONTHLY or None,
        "price_advanced_annual": PAYPAL_PRICE_ADVANCED_ANNUAL or None,
    }


@router.post("/paypal/checkout")
def create_paypal_checkout(payload: PayPalCheckoutRequest):
    amount = _price_for(payload.tier, payload.interval)
    if not amount:
        raise HTTPException(status_code=503, detail="PayPal pricing isn't configured on this deployment.")

    token = _paypal_access_token()
    response = requests.post(
        f"{_paypal_api_base()}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {"currency_code": PAYPAL_CURRENCY, "value": amount},
                    "custom_id": f"{payload.tier}:{payload.interval}",
                }
            ],
            "application_context": {
                "brand_name": "CRM Scoring",
                "user_action": "PAY_NOW",
                "return_url": f"{APP_BASE_URL.rstrip('/')}/thank-you.html",
                "cancel_url": f"{APP_BASE_URL.rstrip('/')}/index.html",
            },
        },
        timeout=10,
    )
    if not response.ok:
        logger.warning("Couldn't create PayPal order: {} {}", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Couldn't create a PayPal checkout.")

    order = response.json()
    approval = next((link["href"] for link in order.get("links", []) if link.get("rel") == "approve"), None)
    if not approval:
        logger.error("PayPal order {} did not include an approval URL.", order.get("id"))
        raise HTTPException(status_code=502, detail="PayPal returned an invalid checkout.")
    return {"url": approval, "order_id": order["id"]}


@router.post("/paypal/capture")
def capture_paypal_order(payload: PayPalCaptureRequest):
    if _already_issued(payload.order_id):
        return {"status": "duplicate"}

    token = _paypal_access_token()
    response = requests.post(
        f"{_paypal_api_base()}/v2/checkout/orders/{payload.order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=10,
    )
    if not response.ok:
        logger.warning("Couldn't capture PayPal order {}: {} {}", payload.order_id, response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Couldn't complete the PayPal payment.")

    order = response.json()
    capture = ((order.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or [{}]
    if capture[0].get("status") != "COMPLETED":
        raise HTTPException(status_code=400, detail="PayPal payment was not completed.")

    custom_id = (order.get("purchase_units") or [{}])[0].get("custom_id", "pro:monthly")
    tier, interval = custom_id.split(":", 1)
    email = (order.get("payer") or {}).get("email_address")
    if not email:
        raise HTTPException(status_code=400, detail="PayPal did not provide a payer email address.")

    _issue_and_deliver(email, interval, tier, payload.order_id)
    return {"status": "ok"}
