"""Seller-side Paddle integration.

Only relevant to the seller's own storefront deployment -- buyers' self-
hosted instances never call these endpoints, they just set LICENSE_KEY in
their .env once they have one. Creates a Paddle transaction for one of two
recurring prices (monthly/annual, see _VALID_INTERVALS) and returns its
hosted checkout URL, and on a verified webhook signs a license key via
../../licensing/issue_license.py, appends it to
licensing/issued_licenses.jsonl, and emails it (services/license_email.py).

Paddle's webhook model is simpler than Stripe's here: a single event,
transaction.completed, fires for both the first payment on checkout and
every later renewal (Paddle represents each charge as its own transaction),
so there's only one issuance path instead of separate
checkout.session.completed / invoice.paid handlers. The plan (and its
validity window) is determined from the completed transaction's line-item
price id, same approach the old Stripe integration used for renewals.

subscription.canceled / transaction.payment_failed: logged only, no new key
issued. An offline-verified key can't be actively revoked once issued, so
the existing key simply lapses at its expiry -- this is why the validity
windows are deliberately short rather than perpetual.

transaction.completed does not include the buyer's email directly (only
customer_id), so a verified webhook makes one follow-up authenticated call
to Paddle's GET /customers/{customer_id} to resolve it.
"""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from ..config import (
    LICENSE_PRIVATE_KEY,
    LICENSE_VALIDITY_DAYS_ANNUAL,
    LICENSE_VALIDITY_DAYS_MONTHLY,
    PADDLE_API_KEY,
    PADDLE_ENVIRONMENT,
    PADDLE_PRICE_ID_ANNUAL,
    PADDLE_PRICE_ID_MONTHLY,
    PADDLE_WEBHOOK_SECRET,
)
from ..services.license_email import send_license_email

_LICENSING_DIR = Path(__file__).resolve().parents[3] / "licensing"
sys.path.insert(0, str(_LICENSING_DIR))
from issue_license import issue_license  # noqa: E402

router = APIRouter(prefix="/api/billing", tags=["billing"])

_ISSUED_LICENSES_LOG = _LICENSING_DIR / "issued_licenses.jsonl"

_VALID_INTERVALS = ("monthly", "annual")

# Signature tolerance: reject a webhook whose timestamp is further from now
# than this, to bound how long a captured request could be replayed --
# mirrors Stripe SDK's default 300s tolerance, which the old integration
# relied on implicitly via stripe.Webhook.construct_event.
_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


def _paddle_api_base() -> str:
    return "https://sandbox-api.paddle.com" if PADDLE_ENVIRONMENT == "sandbox" else "https://api.paddle.com"


def _price_id_for_interval(interval: str) -> str:
    # Bare-global lookups rather than a dict built once at import time, so
    # monkeypatching (tests) or a changed .env actually takes effect.
    return PADDLE_PRICE_ID_ANNUAL if interval == "annual" else PADDLE_PRICE_ID_MONTHLY


def _validity_days_for_interval(interval: str) -> int:
    return LICENSE_VALIDITY_DAYS_ANNUAL if interval == "annual" else LICENSE_VALIDITY_DAYS_MONTHLY


def _interval_for_price_id(price_id: str | None) -> str:
    return "annual" if price_id == PADDLE_PRICE_ID_ANNUAL else "monthly"


def _issue_and_deliver(email: str, plan: str) -> str:
    if not LICENSE_PRIVATE_KEY:
        logger.error("Payment received for {} but LICENSE_PRIVATE_KEY isn't set — can't issue a license.", email)
        raise HTTPException(status_code=500, detail="License signing key not configured on this deployment.")

    days = _validity_days_for_interval(plan)
    license_key = issue_license(email, plan=plan, private_key_b64=LICENSE_PRIVATE_KEY, days=days)

    _ISSUED_LICENSES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _ISSUED_LICENSES_LOG.open("a") as f:
        f.write(json.dumps({"email": email, "license_key": license_key, "issued_at": time.time()}) + "\n")

    emailed = send_license_email(email, license_key, plan)
    logger.info(
        "Issued license for {} ({}){}",
        email,
        plan,
        "" if emailed else " — not emailed, see licensing/issued_licenses.jsonl",
    )
    return license_key


def _fetch_customer_email(customer_id: str) -> str | None:
    resp = requests.get(
        f"{_paddle_api_base()}/customers/{customer_id}",
        headers={"Authorization": f"Bearer {PADDLE_API_KEY}"},
        timeout=10,
    )
    if not resp.ok:
        logger.warning("Couldn't fetch Paddle customer {}: {} {}", customer_id, resp.status_code, resp.text)
        return None
    return resp.json().get("data", {}).get("email")


@router.post("/checkout")
def create_checkout_session(interval: str = "monthly"):
    if interval not in _VALID_INTERVALS:
        raise HTTPException(status_code=400, detail="interval must be 'monthly' or 'annual'.")

    price_id = _price_id_for_interval(interval)
    if not PADDLE_API_KEY or not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Paddle isn't configured for the {interval} plan on this deployment "
            f"(PADDLE_API_KEY / PADDLE_PRICE_ID_{interval.upper()} missing).",
        )

    resp = requests.post(
        f"{_paddle_api_base()}/transactions",
        headers={"Authorization": f"Bearer {PADDLE_API_KEY}"},
        json={"items": [{"price_id": price_id, "quantity": 1}]},
        timeout=10,
    )
    if not resp.ok:
        logger.error("Paddle transaction create failed: {} {}", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Couldn't start checkout with Paddle.")

    checkout_url = resp.json().get("data", {}).get("checkout", {}).get("url")
    if not checkout_url:
        logger.error("Paddle transaction response had no checkout.url: {}", resp.text)
        raise HTTPException(status_code=502, detail="Paddle didn't return a checkout URL.")

    return {"checkout_url": checkout_url}


def _verify_paddle_signature(raw_body: bytes, signature_header: str) -> bool:
    parts = dict(part.split("=", 1) for part in signature_header.split(";") if "=" in part)
    ts, h1 = parts.get("ts"), parts.get("h1")
    if not ts or not h1:
        return False
    if abs(time.time() - int(ts)) > _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
        return False

    signed_payload = f"{ts}:{raw_body.decode()}"
    computed = hmac.new(PADDLE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, h1)


@router.post("/webhook")
async def paddle_webhook(request: Request):
    if not PADDLE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="PADDLE_WEBHOOK_SECRET not configured.")

    raw_body = await request.body()
    signature_header = request.headers.get("paddle-signature", "")

    try:
        valid = _verify_paddle_signature(raw_body, signature_header)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event = json.loads(raw_body)
    event_type = event["event_type"]
    data = event["data"]

    if event_type == "transaction.completed":
        customer_id = data.get("customer_id")
        if not customer_id:
            logger.warning("transaction.completed with no customer_id; can't issue a license.")
            return {"status": "ignored"}

        email = _fetch_customer_email(customer_id)
        if not email:
            logger.warning("Couldn't resolve an email for Paddle customer {}; can't issue a license.", customer_id)
            return {"status": "ignored"}

        line_price_id = ((data.get("items") or [{}])[0].get("price") or {}).get("id")
        _issue_and_deliver(email, plan=_interval_for_price_id(line_price_id))

    elif event_type in ("subscription.canceled", "transaction.payment_failed"):
        logger.info(
            "Subscription event {} for customer {} — no new license issued, existing key lapses at its own expiry.",
            event_type,
            data.get("customer_id", "(unknown customer)"),
        )

    return {"status": "ok"}
