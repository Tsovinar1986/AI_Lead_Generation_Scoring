import json

import pytest
from fastapi import HTTPException

from app.routers import billing

PLANS = {
    "PAYPAL_PLAN_PRO_MONTHLY": "P-PRO-M",
    "PAYPAL_PLAN_PRO_ANNUAL": "P-PRO-A",
    "PAYPAL_PLAN_ADVANCED_MONTHLY": "P-ADV-M",
    "PAYPAL_PLAN_ADVANCED_ANNUAL": "P-ADV-A",
}


def _subscription(sub_id="I-1", plan_id="P-PRO-M", status="ACTIVE", next_billing="2026-10-25T10:00:00Z"):
    return {
        "id": sub_id,
        "status": status,
        "plan_id": plan_id,
        "subscriber": {"email_address": "buyer@example.com"},
        "billing_info": {"next_billing_time": next_billing},
    }


@pytest.fixture
def paypal(monkeypatch, tmp_path):
    """Stub PayPal and license issuing; records every issued transaction id."""
    issued = []
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", tmp_path / "issued.jsonl")
    monkeypatch.setattr(billing, "_paypal_access_token", lambda: "token")
    monkeypatch.setattr(billing, "PAYPAL_WEBHOOK_ID", "WH-1")
    monkeypatch.setattr(billing, "STOREFRONT_URL", "https://shop.example")
    for name, value in PLANS.items():
        monkeypatch.setattr(billing, name, value)

    def fake_issue(email, interval, tier, transaction_id):
        issued.append((transaction_id, tier, interval))
        with billing._ISSUED_LICENSES_LOG.open("a") as log:
            log.write(json.dumps({"transaction_id": transaction_id}) + "\n")
        return "key"

    monkeypatch.setattr(billing, "_issue_and_deliver", fake_issue)
    return issued


def test_billing_config_exposes_plans_and_public_client_id_only(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_ID", "public-client")
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_SECRET", "top-secret")

    body = client.get("/api/billing/config").json()

    assert body["paypal_available"] is True
    assert body["client_id"] == "public-client"
    assert body["plans"] == {
        "pro_monthly": "P-PRO-M",
        "pro_annual": "P-PRO-A",
        "advanced_monthly": "P-ADV-M",
        "advanced_annual": "P-ADV-A",
    }
    assert "top-secret" not in json.dumps(body)


def test_billing_config_unavailable_without_plans(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_ID", "client")
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setattr(billing, "PAYPAL_PLAN_ADVANCED_ANNUAL", "")

    assert client.get("/api/billing/config").json()["paypal_available"] is False


def test_checkout_requires_plan(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "PAYPAL_PLAN_PRO_MONTHLY", "")

    response = client.post("/api/billing/paypal/checkout", json={"interval": "monthly", "tier": "pro"})

    assert response.status_code == 503


def test_activate_returns_license_to_first_caller_only(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, "P-ADV-A"))

    first = client.post("/api/billing/paypal/subscription/activate", json={"subscription_id": "I-1"})
    second = client.post("/api/billing/paypal/subscription/activate", json={"subscription_id": "I-1"})

    assert first.json() == {
        "status": "ok",
        "email": "buyer@example.com",
        "tier": "advanced",
        "plan": "annual",
        "license_key": "key",
    }
    assert second.json() == {"status": "duplicate"}
    assert [(tier, interval) for _, tier, interval in paypal] == [("advanced", "annual")]


def test_activate_rejects_unknown_plan(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, "P-SOMEONE-ELSE"))

    response = client.post("/api/billing/paypal/subscription/activate", json={"subscription_id": "I-1"})

    assert response.status_code == 400
    assert paypal == []


def test_activate_waits_for_active_status(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, status="APPROVED"))

    response = client.post("/api/billing/paypal/subscription/activate", json={"subscription_id": "I-1"})

    assert response.status_code == 409
    assert paypal == []


def test_return_activates_and_redirects_to_storefront(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id))

    response = client.get("/api/billing/paypal/return?subscription_id=I-1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "https://shop.example/thank-you.html?status=ok"
    assert len(paypal) == 1


def test_return_reports_pending_when_not_yet_active(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, status="APPROVED"))

    response = client.get("/api/billing/paypal/return?subscription_id=I-1", follow_redirects=False)

    assert response.headers["location"].endswith("status=pending")


def test_return_reports_failure_when_paypal_errors(client, monkeypatch, paypal):
    def boom(sub_id):
        raise HTTPException(status_code=502, detail="nope")

    monkeypatch.setattr(billing, "_get_subscription", boom)

    response = client.get("/api/billing/paypal/return?subscription_id=I-1", follow_redirects=False)

    assert response.headers["location"].endswith("status=failed")
    assert paypal == []


def test_webhook_rejects_bad_signature(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_verify_webhook", lambda request, event: False)

    response = client.post(
        "/api/billing/paypal/webhook", json={"event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-1"}}
    )

    assert response.status_code == 400
    assert paypal == []


def test_webhook_activation_then_first_sale_issue_one_key(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_verify_webhook", lambda request, event: True)
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id))

    activated = client.post(
        "/api/billing/paypal/webhook", json={"event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-1"}}
    )
    sale = client.post(
        "/api/billing/paypal/webhook",
        json={"event_type": "PAYMENT.SALE.COMPLETED", "resource": {"id": "S-1", "billing_agreement_id": "I-1"}},
    )

    assert activated.json() == {"status": "ok"}
    assert sale.json() == {"status": "duplicate"}
    assert len(paypal) == 1


def test_webhook_renewal_issues_a_fresh_key(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_verify_webhook", lambda request, event: True)
    sale = {"event_type": "PAYMENT.SALE.COMPLETED", "resource": {"billing_agreement_id": "I-1"}}

    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, next_billing="2026-10-25T10:00:00Z"))
    client.post("/api/billing/paypal/webhook", json=sale)
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, next_billing="2026-11-25T10:00:00Z"))
    renewal = client.post("/api/billing/paypal/webhook", json=sale)

    assert renewal.json() == {"status": "ok"}
    assert [tx for tx, _, _ in paypal] == ["I-1@2026-10-25T10:00:00Z", "I-1@2026-11-25T10:00:00Z"]


def test_webhook_ignores_other_events(client, monkeypatch, paypal):
    monkeypatch.setattr(billing, "_verify_webhook", lambda request, event: True)

    response = client.post(
        "/api/billing/paypal/webhook", json={"event_type": "BILLING.SUBSCRIPTION.CANCELLED", "resource": {"id": "I-1"}}
    )

    assert response.json() == {"status": "ignored"}
    assert paypal == []


def test_webhook_verification_needs_webhook_id(monkeypatch, paypal):
    monkeypatch.setattr(billing, "PAYPAL_WEBHOOK_ID", "")

    assert billing._verify_webhook(None, {}) is False
