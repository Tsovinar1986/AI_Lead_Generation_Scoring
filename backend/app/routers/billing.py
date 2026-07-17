"""Seller-side Stripe integration.

Only relevant to the seller's own storefront deployment -- buyers' self-
hosted instances never call these endpoints, they just set LICENSE_KEY in
their .env once they have one. Creates a Checkout Session for one of two
recurring prices (monthly/annual, see _VALID_INTERVALS), and on payment
events (verified webhook) signs a license key via ../../licensing/issue_license.py,
appends it to licensing/issued_licenses.jsonl, and emails it
(services/license_email.py).

Subscription lifecycle (STRIPE_BILLING_MODE=subscription, the default):
- checkout.session.completed: first payment succeeds -> issue a license for
  the plan in the Session's metadata, valid for that plan's
  LICENSE_VALIDITY_DAYS_{MONTHLY,ANNUAL}.
- invoice.paid: fires every renewal -> issue a fresh license, with the plan
  (and its validity window) determined from the invoice line item's price
  id rather than trusting metadata to have propagated, so an active
  subscriber's key never expires in practice.
- customer.subscription.deleted / invoice.payment_failed: logged only, no
  new key issued. An offline-verified key can't be actively revoked once
  issued, so the existing key simply lapses at its expiry -- this is why
  the validity windows are deliberately short rather than perpetual.

One-time mode (STRIPE_BILLING_MODE=payment) only ever handles
checkout.session.completed and issues a perpetual (no-expiry) license.
"""

import json
import sys
import time
from pathlib import Path

import stripe
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from ..config import (
    LICENSE_PRIVATE_KEY,
    LICENSE_VALIDITY_DAYS_ANNUAL,
    LICENSE_VALIDITY_DAYS_MONTHLY,
    STRIPE_BILLING_MODE,
    STRIPE_CANCEL_URL,
    STRIPE_PRICE_ID_ANNUAL,
    STRIPE_PRICE_ID_MONTHLY,
    STRIPE_SECRET_KEY,
    STRIPE_SUCCESS_URL,
    STRIPE_WEBHOOK_SECRET,
)
from ..services.license_email import send_license_email

_LICENSING_DIR = Path(__file__).resolve().parents[3] / "licensing"
sys.path.insert(0, str(_LICENSING_DIR))
from issue_license import issue_license  # noqa: E402

router = APIRouter(prefix="/api/billing", tags=["billing"])

_ISSUED_LICENSES_LOG = _LICENSING_DIR / "issued_licenses.jsonl"

_VALID_INTERVALS = ("monthly", "annual")


def _price_id_for_interval(interval: str) -> str:
    # Bare-global lookups rather than a dict built once at import time, so
    # monkeypatching (tests) or a changed .env actually takes effect.
    return STRIPE_PRICE_ID_ANNUAL if interval == "annual" else STRIPE_PRICE_ID_MONTHLY


def _validity_days_for_interval(interval: str) -> int:
    return LICENSE_VALIDITY_DAYS_ANNUAL if interval == "annual" else LICENSE_VALIDITY_DAYS_MONTHLY


def _interval_for_price_id(price_id: str | None) -> str:
    """Renewals (invoice.paid) carry the price actually billed, which is the
    source of truth for which validity window to reissue with -- more
    robust than trusting metadata to have propagated from the original
    Checkout Session onto the subscription."""
    return "annual" if price_id == STRIPE_PRICE_ID_ANNUAL else "monthly"


def _issue_and_deliver(email: str, plan: str) -> str:
    if not LICENSE_PRIVATE_KEY:
        logger.error("Payment received for {} but LICENSE_PRIVATE_KEY isn't set — can't issue a license.", email)
        raise HTTPException(status_code=500, detail="License signing key not configured on this deployment.")

    days = _validity_days_for_interval(plan) if STRIPE_BILLING_MODE == "subscription" else None
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


@router.post("/checkout")
def create_checkout_session(interval: str = "monthly"):
    if interval not in _VALID_INTERVALS:
        raise HTTPException(status_code=400, detail="interval must be 'monthly' or 'annual'.")

    price_id = _price_id_for_interval(interval)
    if not STRIPE_SECRET_KEY or not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe isn't configured for the {interval} plan on this deployment "
            f"(STRIPE_SECRET_KEY / STRIPE_PRICE_ID_{interval.upper()} missing).",
        )

    stripe.api_key = STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode=STRIPE_BILLING_MODE,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=STRIPE_SUCCESS_URL,
        cancel_url=STRIPE_CANCEL_URL,
        # Read back on checkout.session.completed to know which plan to
        # issue -- the Session object doesn't otherwise expose its price
        # without a separate line-items fetch.
        metadata={"interval": interval},
    )
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET not configured.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        # construct_event's only job here is signature verification -- its
        # return value is a StripeObject, whose shape/available methods (e.g.
        # whether .get() exists) has changed across SDK major versions. Read
        # the actual event data back out of the raw, already-verified
        # payload instead, so this doesn't break on the next stripe-python bump.
        stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

    event = json.loads(payload)
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        email = (data.get("customer_details") or {}).get("email")
        if not email:
            logger.warning("Checkout completed with no customer email; can't issue a license.")
            return {"status": "ignored"}
        interval = (data.get("metadata") or {}).get("interval", "monthly")
        _issue_and_deliver(email, plan=interval if interval in _VALID_INTERVALS else "monthly")

    elif event_type == "invoice.paid":
        # Fires on every renewal, including the first one right after
        # checkout.session.completed for subscription mode -- issuing again
        # here is harmless (just extends the expiry further), so no need to
        # special-case "first invoice vs renewal."
        email = data.get("customer_email")
        if not email:
            logger.warning("invoice.paid with no customer_email; can't renew a license.")
            return {"status": "ignored"}
        line_price_id = ((data.get("lines") or {}).get("data") or [{}])[0].get("price", {}).get("id")
        _issue_and_deliver(email, plan=_interval_for_price_id(line_price_id))

    elif event_type in ("customer.subscription.deleted", "invoice.payment_failed"):
        email = (data.get("customer_email") or (data.get("customer_details") or {}).get("email"))
        logger.info(
            "Subscription event {} for {} — no new license issued, existing key lapses at its own expiry.",
            event_type,
            email or "(unknown customer)",
        )

    return {"status": "ok"}
