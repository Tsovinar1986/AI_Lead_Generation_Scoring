import base64
import json
import time

import stripe

from app.routers import billing


def _sign(payload_str: str, secret: str) -> str:
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload_str}", secret)
    return f"t={ts},v1={sig}"


def _event(event_type: str, obj: dict) -> tuple[bytes, str]:
    payload_str = json.dumps({"id": "evt_test", "object": "event", "type": event_type, "data": {"object": obj}})
    return payload_str.encode(), _sign(payload_str, "whsec_test")


def _decode_license_payload(license_key: str) -> dict:
    payload_b64 = license_key.split(".", 1)[0]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_checkout_without_stripe_config_returns_503(client, monkeypatch):
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_MONTHLY", "")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_ANNUAL", "")

    resp = client.post("/api/billing/checkout")
    assert resp.status_code == 503


def test_checkout_rejects_unknown_interval(client):
    resp = client.post("/api/billing/checkout?interval=weekly")
    assert resp.status_code == 400


def test_checkout_annual_missing_price_returns_503_even_if_monthly_configured(client, monkeypatch):
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_MONTHLY", "price_monthly")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_ANNUAL", "")

    resp = client.post("/api/billing/checkout?interval=annual")
    assert resp.status_code == 503


def test_webhook_without_secret_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "")

    resp = client.post("/api/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"})
    assert resp.status_code == 503


def test_webhook_rejects_tampered_signature(client, monkeypatch):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    resp = client.post(
        "/api/billing/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert resp.status_code == 400


def test_checkout_completed_issues_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("checkout.session.completed", {"customer_details": {"email": "buyer@example.com"}})
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["email"] == "buyer@example.com"


def test_checkout_completed_with_annual_metadata_issues_annual_validity(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    monkeypatch.setattr(billing, "LICENSE_VALIDITY_DAYS_ANNUAL", 380)
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event(
        "checkout.session.completed",
        {"customer_details": {"email": "buyer@example.com"}, "metadata": {"interval": "annual"}},
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    license_key = json.loads(log_path.read_text().splitlines()[0])["license_key"]
    issued = _decode_license_payload(license_key)
    assert issued["plan"] == "annual"
    assert round((issued["expires_at"] - issued["issued_at"]) / 86400) == 380


def test_invoice_paid_reissues_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("invoice.paid", {"customer_email": "buyer@example.com"})
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    assert len(log_path.read_text().splitlines()) == 1


def test_invoice_paid_maps_billed_price_to_annual_plan(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_ANNUAL", "price_annual_123")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event(
        "invoice.paid",
        {
            "customer_email": "buyer@example.com",
            "lines": {"data": [{"price": {"id": "price_annual_123"}}]},
        },
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    license_key = json.loads(log_path.read_text().splitlines()[0])["license_key"]
    assert _decode_license_payload(license_key)["plan"] == "annual"


def test_subscription_deleted_issues_no_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("customer.subscription.deleted", {"customer_email": "buyer@example.com"})
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    assert not log_path.exists()


def test_checkout_completed_without_email_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("checkout.session.completed", {"customer_details": {}})
    resp = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig})

    assert resp.status_code == 200
    assert not log_path.exists()
