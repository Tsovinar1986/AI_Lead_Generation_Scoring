"""PayPal Subscriptions and license delivery for the seller storefront.

Starter is free (no PayPal plan). Pro and Advanced each have a monthly and an
annual PayPal billing plan (create them with backend/scripts/create_paypal_plans.py).
A license key is issued when a subscription activates and again on every
renewal payment, each one valid a little past the next billing date -- so a
cancelled subscription simply stops getting fresh keys.
"""

import json
import sys
import threading
import time
from pathlib import Path
from typing import Literal

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import (
    LICENSE_PRIVATE_KEY,
    LICENSE_VALIDITY_DAYS_ANNUAL,
    LICENSE_VALIDITY_DAYS_MONTHLY,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_CURRENCY,
    PAYPAL_ENVIRONMENT,
    PAYPAL_PLAN_ADVANCED_ANNUAL,
    PAYPAL_PLAN_ADVANCED_MONTHLY,
    PAYPAL_PLAN_PRO_ANNUAL,
    PAYPAL_PLAN_PRO_MONTHLY,
    PAYPAL_PRICE_ADVANCED_ANNUAL,
    PAYPAL_PRICE_ADVANCED_MONTHLY,
    PAYPAL_PRICE_ANNUAL,
    PAYPAL_PRICE_MONTHLY,
    PAYPAL_WEBHOOK_ID,
    STOREFRONT_URL,
)
from ..services.license_email import send_license_email

_LICENSING_DIR = Path(__file__).resolve().parents[3] / "licensing"
sys.path.insert(0, str(_LICENSING_DIR))
from issue_license import issue_license  # noqa: E402

router = APIRouter(prefix="/api/billing", tags=["billing"])
_ISSUED_LICENSES_LOG = _LICENSING_DIR / "issued_licenses.jsonl"
# The in-page approval, the return redirect and the webhooks can all try to
# fulfil the same billing period at nearly the same moment -- serialise the
# check-then-issue so one payment never produces two keys.
_fulfil_lock = threading.Lock()

Tier = Literal["pro", "advanced"]
Interval = Literal["monthly", "annual"]


def _paypal_api_base() -> str:
    return "https://api-m.sandbox.paypal.com" if PAYPAL_ENVIRONMENT == "sandbox" else "https://api-m.paypal.com"


def _storefront(path: str) -> str:
    return f"{STOREFRONT_URL.rstrip('/')}/{path}"


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


def _paypal_headers() -> dict:
    return {"Authorization": f"Bearer {_paypal_access_token()}", "Content-Type": "application/json"}


def _plans() -> dict[tuple[str, str], str]:
    return {
        ("pro", "monthly"): PAYPAL_PLAN_PRO_MONTHLY,
        ("pro", "annual"): PAYPAL_PLAN_PRO_ANNUAL,
        ("advanced", "monthly"): PAYPAL_PLAN_ADVANCED_MONTHLY,
        ("advanced", "annual"): PAYPAL_PLAN_ADVANCED_ANNUAL,
    }


def _plan_for(tier: str, interval: str) -> str:
    return _plans().get((tier, interval), "")


def _tier_for_plan(plan_id: str) -> tuple[str, str] | None:
    """Map a PayPal plan id back to (tier, interval); None if it isn't ours."""
    for key, value in _plans().items():
        if value and value == plan_id:
            return key
    return None


def _validity_days(interval: str) -> int:
    return LICENSE_VALIDITY_DAYS_ANNUAL if interval == "annual" else LICENSE_VALIDITY_DAYS_MONTHLY


def _already_issued(transaction_id: str) -> bool:
    if not _ISSUED_LICENSES_LOG.exists():
        return False
    with _ISSUED_LICENSES_LOG.open() as log:
        for line in log:
            try:
                if json.loads(line).get("transaction_id") == transaction_id:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def _issue_and_deliver(email: str, interval: str, tier: str, transaction_id: str) -> str:
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
                    "transaction_id": transaction_id,
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


def _get_subscription(subscription_id: str) -> dict:
    response = requests.get(
        f"{_paypal_api_base()}/v1/billing/subscriptions/{subscription_id}", headers=_paypal_headers(), timeout=10
    )
    if not response.ok:
        logger.warning("Couldn't fetch PayPal subscription {}: {} {}", subscription_id, response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Couldn't look up the PayPal subscription.")
    return response.json()


def _fulfil(subscription: dict) -> dict:
    """Issue a key for the subscription's current billing period, at most once.

    A period is identified by (subscription id, next billing time): activation
    and the first PAYMENT.SALE.COMPLETED share one, and each renewal moves
    next_billing_time forward, so it gets a fresh key.
    """
    subscription_id = subscription.get("id", "")
    if subscription.get("status") != "ACTIVE":
        raise HTTPException(status_code=409, detail="PayPal subscription isn't active yet.")

    plan = _tier_for_plan(subscription.get("plan_id", ""))
    if plan is None:
        logger.error("PayPal subscription {} is on unknown plan {}.", subscription_id, subscription.get("plan_id"))
        raise HTTPException(status_code=400, detail="PayPal subscription is for an unknown plan.")
    tier, interval = plan

    email = (subscription.get("subscriber") or {}).get("email_address")
    if not email:
        raise HTTPException(status_code=400, detail="PayPal did not provide a subscriber email address.")

    period = (subscription.get("billing_info") or {}).get("next_billing_time", "")
    transaction_id = f"{subscription_id}@{period}"
    with _fulfil_lock:
        if _already_issued(transaction_id):
            return {"status": "duplicate"}
        license_key = _issue_and_deliver(email, interval, tier, transaction_id)
    return {"status": "ok", "email": email, "tier": tier, "plan": interval, "license_key": license_key}


class SubscriptionCheckoutRequest(BaseModel):
    interval: Interval
    tier: Tier = "pro"


class SubscriptionActivateRequest(BaseModel):
    subscription_id: str


@router.get("/config")
def billing_config():
    plans = {f"{tier}_{interval}": plan_id or None for (tier, interval), plan_id in _plans().items()}
    return {
        "paypal_available": bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET and all(plans.values())),
        # Public by design -- PayPal's JS SDK needs it in the browser to
        # render the in-page buttons. The secret never leaves the server.
        "client_id": PAYPAL_CLIENT_ID or None,
        "plans": plans,
        "currency": PAYPAL_CURRENCY,
        "environment": PAYPAL_ENVIRONMENT,
        "price_monthly": PAYPAL_PRICE_MONTHLY or None,
        "price_annual": PAYPAL_PRICE_ANNUAL or None,
        "price_advanced_monthly": PAYPAL_PRICE_ADVANCED_MONTHLY or None,
        "price_advanced_annual": PAYPAL_PRICE_ADVANCED_ANNUAL or None,
    }


@router.post("/paypal/checkout")
def create_paypal_subscription(payload: SubscriptionCheckoutRequest, request: Request):
    """Redirect-style checkout, for the static storefront (docs/index.html).

    The in-app React frontend uses PayPal's JS SDK buttons instead and calls
    /paypal/subscription/activate itself.
    """
    plan_id = _plan_for(payload.tier, payload.interval)
    if not plan_id:
        raise HTTPException(status_code=503, detail="PayPal plans aren't configured on this deployment.")

    response = requests.post(
        f"{_paypal_api_base()}/v1/billing/subscriptions",
        headers=_paypal_headers(),
        json={
            "plan_id": plan_id,
            "application_context": {
                "brand_name": "CRM Scoring",
                "user_action": "SUBSCRIBE_NOW",
                "shipping_preference": "NO_SHIPPING",
                # Back to this backend, so activation is handled server-side
                # before the buyer lands on the storefront's thank-you page.
                "return_url": str(request.url_for("paypal_return")),
                "cancel_url": _storefront("index.html#pricing"),
            },
        },
        timeout=10,
    )
    if not response.ok:
        logger.warning("Couldn't create PayPal subscription: {} {}", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Couldn't create a PayPal checkout.")

    subscription = response.json()
    approval = next((link["href"] for link in subscription.get("links", []) if link.get("rel") == "approve"), None)
    if not approval:
        logger.error("PayPal subscription {} did not include an approval URL.", subscription.get("id"))
        raise HTTPException(status_code=502, detail="PayPal returned an invalid checkout.")
    return {"url": approval, "subscription_id": subscription["id"]}


@router.get("/paypal/return", name="paypal_return")
def paypal_return(subscription_id: str = ""):
    """PayPal sends the buyer here after approving (?subscription_id=...)."""
    status = "failed"
    if subscription_id:
        try:
            _fulfil(_get_subscription(subscription_id))
            status = "ok"
        except HTTPException as exc:
            # 409 = approved but PayPal hasn't activated it yet; the
            # BILLING.SUBSCRIPTION.ACTIVATED webhook will issue the key.
            status = "pending" if exc.status_code == 409 else "failed"
            logger.warning("PayPal return for subscription {}: {}", subscription_id, exc.detail)
    return RedirectResponse(_storefront(f"thank-you.html?status={status}"), status_code=303)


@router.post("/paypal/subscription/activate")
def activate_paypal_subscription(payload: SubscriptionActivateRequest):
    # Returns the key only to the first caller -- the buyer's own browser in
    # the in-page flow. Repeat calls just say "duplicate".
    return _fulfil(_get_subscription(payload.subscription_id))


def _verify_webhook(request: Request, event: dict) -> bool:
    if not PAYPAL_WEBHOOK_ID:
        logger.error("PayPal webhook received but PAYPAL_WEBHOOK_ID isn't set; rejecting.")
        return False
    h = request.headers
    response = requests.post(
        f"{_paypal_api_base()}/v1/notifications/verify-webhook-signature",
        headers=_paypal_headers(),
        json={
            "auth_algo": h.get("paypal-auth-algo"),
            "cert_url": h.get("paypal-cert-url"),
            "transmission_id": h.get("paypal-transmission-id"),
            "transmission_sig": h.get("paypal-transmission-sig"),
            "transmission_time": h.get("paypal-transmission-time"),
            "webhook_id": PAYPAL_WEBHOOK_ID,
            "webhook_event": event,
        },
        timeout=10,
    )
    return response.ok and response.json().get("verification_status") == "SUCCESS"


@router.post("/paypal/webhook")
async def paypal_webhook(request: Request):
    """Activation fallback and renewals.

    Subscribe the webhook (PayPal developer dashboard -> your app ->
    Webhooks) to BILLING.SUBSCRIPTION.ACTIVATED and PAYMENT.SALE.COMPLETED.
    """
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON.")
    # Everything below makes blocking PayPal API calls -- keep them off the
    # event loop.
    return await run_in_threadpool(_handle_webhook, request, event)


def _handle_webhook(request: Request, event: dict) -> dict:
    if not _verify_webhook(request, event):
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")

    event_type = event.get("event_type")
    resource = event.get("resource") or {}
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        subscription_id = resource.get("id")
    elif event_type == "PAYMENT.SALE.COMPLETED":
        subscription_id = resource.get("billing_agreement_id")
    else:
        if event_type and event_type.startswith("BILLING.SUBSCRIPTION."):
            # Cancelled/suspended/expired: nothing to revoke -- the last key
            # just runs out, since no renewal will issue a new one.
            logger.info("PayPal {} for subscription {}", event_type, resource.get("id"))
        return {"status": "ignored"}
    if not subscription_id:
        return {"status": "ignored"}

    try:
        result = _fulfil(_get_subscription(subscription_id))
    except HTTPException as exc:
        # 4xx here means the subscription itself is unusable -- acknowledge
        # it so PayPal stops retrying. 5xx/502s propagate and PayPal retries.
        if exc.status_code < 500:
            logger.warning("PayPal webhook {} for {} not fulfilled: {}", event_type, subscription_id, exc.detail)
            return {"status": "rejected"}
        raise
    return {"status": result["status"]}
