import json
from datetime import date
from types import SimpleNamespace

import braintree
import pytest
from fastapi import HTTPException

from app.routers import billing

PLANS = {
    "BRAINTREE_PLAN_PRO_MONTHLY": "pro-m",
    "BRAINTREE_PLAN_PRO_ANNUAL": "pro-a",
    "BRAINTREE_PLAN_ADVANCED_MONTHLY": "adv-m",
    "BRAINTREE_PLAN_ADVANCED_ANNUAL": "adv-a",
}
Kind = braintree.WebhookNotification.Kind


def _subscription(sub_id="sub1", plan_id="pro-m", status="Active", paid_through=date(2026, 10, 25)):
    return SimpleNamespace(
        id=sub_id, status=status, plan_id=plan_id, paid_through_date=paid_through, payment_method_token="pm1"
    )


def _result(ok, **attrs):
    return SimpleNamespace(is_success=ok, message=attrs.pop("message", None), **attrs)


class FakeGateway:
    """Stands in for braintree.BraintreeGateway; records what checkout sent."""

    def __init__(self):
        self.customer_params = None
        self.subscription_params = None
        self.customer_result = _result(
            True, customer=SimpleNamespace(payment_methods=[SimpleNamespace(token="pm1")])
        )
        self.subscription_result = _result(True, subscription=_subscription())
        self.customer = SimpleNamespace(create=self._create_customer)
        self.subscription = SimpleNamespace(create=self._create_subscription)
        self.client_token = SimpleNamespace(generate=lambda: "client-token")

    def _create_customer(self, params):
        self.customer_params = params
        return self.customer_result

    def _create_subscription(self, params):
        self.subscription_params = params
        return self.subscription_result


@pytest.fixture
def braintree_stub(monkeypatch, tmp_path):
    """Stub Braintree and license issuing; records every issued transaction id."""
    issued = []
    gateway = FakeGateway()
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", tmp_path / "issued.jsonl")
    monkeypatch.setattr(billing, "_gateway", lambda: gateway)
    monkeypatch.setattr(billing, "_subscriber_email", lambda sub: "buyer@example.com")
    monkeypatch.setattr(billing, "BRAINTREE_MERCHANT_ID", "merchant")
    monkeypatch.setattr(billing, "BRAINTREE_PUBLIC_KEY", "public")
    monkeypatch.setattr(billing, "BRAINTREE_PRIVATE_KEY", "top-secret")
    for name, value in PLANS.items():
        monkeypatch.setattr(billing, name, value)
    billing.limiter.reset()

    def fake_issue(email, interval, tier, transaction_id):
        issued.append((transaction_id, tier, interval))
        with billing._ISSUED_LICENSES_LOG.open("a") as log:
            log.write(json.dumps({"transaction_id": transaction_id}) + "\n")
        return "key"

    monkeypatch.setattr(billing, "_issue_and_deliver", fake_issue)
    gateway.issued = issued
    return gateway


def _checkout(client, **overrides):
    body = {"interval": "monthly", "tier": "pro", "email": "buyer@example.com", "payment_method_nonce": "nonce"}
    return client.post("/api/billing/braintree/subscribe", json={**body, **overrides})


def _webhook(client, monkeypatch, kind, subscription_id="sub1"):
    notification = SimpleNamespace(kind=kind, subscription=SimpleNamespace(id=subscription_id))
    monkeypatch.setattr(billing, "_parse_webhook", lambda signature, payload: notification)
    return client.post("/api/billing/braintree/webhook", data={"bt_signature": "sig", "bt_payload": "payload"})


def test_billing_config_exposes_plans_but_no_secrets(client, braintree_stub):
    body = client.get("/api/billing/config").json()

    assert body["checkout_available"] is True
    assert body["plans"] == {
        "pro_monthly": "pro-m",
        "pro_annual": "pro-a",
        "advanced_monthly": "adv-m",
        "advanced_annual": "adv-a",
    }
    assert "top-secret" not in json.dumps(body)


def test_billing_config_unavailable_without_keys(client, monkeypatch, braintree_stub):
    monkeypatch.setattr(billing, "BRAINTREE_PRIVATE_KEY", "")

    assert client.get("/api/billing/config").json()["checkout_available"] is False


def test_client_token(client, braintree_stub):
    assert client.get("/api/billing/braintree/client-token").json() == {"client_token": "client-token"}


def test_gateway_requires_keys(monkeypatch):
    monkeypatch.setattr(billing, "BRAINTREE_MERCHANT_ID", "")

    with pytest.raises(HTTPException) as exc:
        billing._gateway()
    assert exc.value.status_code == 503


def test_subscribe_vaults_card_and_returns_license(client, braintree_stub):
    braintree_stub.subscription_result = _result(True, subscription=_subscription(plan_id="adv-a"))

    response = _checkout(client, tier="advanced", interval="annual", device_data="dd")

    assert response.json() == {
        "status": "ok",
        "email": "buyer@example.com",
        "tier": "advanced",
        "plan": "annual",
        "license_key": "key",
    }
    assert braintree_stub.customer_params == {
        "email": "buyer@example.com",
        "payment_method_nonce": "nonce",
        "credit_card": {"options": {"verify_card": True}},
        "device_data": "dd",
    }
    assert braintree_stub.subscription_params == {"payment_method_token": "pm1", "plan_id": "adv-a"}
    assert braintree_stub.issued == [("sub1@2026-10-25", "advanced", "annual")]


def test_subscribe_requires_plan(client, monkeypatch, braintree_stub):
    monkeypatch.setattr(billing, "BRAINTREE_PLAN_PRO_MONTHLY", "")

    assert _checkout(client).status_code == 503


def test_subscribe_reports_declined_card(client, braintree_stub):
    braintree_stub.customer_result = _result(
        False, message="Do Not Honor", credit_card_verification=SimpleNamespace(status="processor_declined")
    )

    response = _checkout(client)

    assert response.status_code == 402
    assert response.json()["detail"] == "Your card was declined. Please try a different card."
    assert braintree_stub.subscription_params is None
    assert braintree_stub.issued == []


def test_subscribe_reports_failed_subscription(client, braintree_stub):
    braintree_stub.subscription_result = _result(False, message="Insufficient Funds", credit_card_verification=None)

    response = _checkout(client)

    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient Funds"
    assert braintree_stub.issued == []


def test_subscribe_rejects_bad_email(client, braintree_stub):
    assert _checkout(client, email="not-an-email").status_code == 422


def test_fulfil_rejects_unknown_plan(braintree_stub):
    with pytest.raises(HTTPException) as exc:
        billing._fulfil(_subscription(plan_id="someone-else"))
    assert exc.value.status_code == 400
    assert braintree_stub.issued == []


def test_fulfil_waits_for_active_status(braintree_stub):
    with pytest.raises(HTTPException) as exc:
        billing._fulfil(_subscription(status="Pending"))
    assert exc.value.status_code == 409


def test_checkout_then_first_charge_webhook_issue_one_key(client, monkeypatch, braintree_stub):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id))

    checkout = _checkout(client)
    charged = _webhook(client, monkeypatch, Kind.SubscriptionChargedSuccessfully)

    assert checkout.json()["status"] == "ok"
    assert charged.json() == {"status": "duplicate"}
    assert len(braintree_stub.issued) == 1


def test_webhook_renewal_issues_a_fresh_key(client, monkeypatch, braintree_stub):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, paid_through=date(2026, 10, 25)))
    _webhook(client, monkeypatch, Kind.SubscriptionChargedSuccessfully)
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, paid_through=date(2026, 11, 25)))
    renewal = _webhook(client, monkeypatch, Kind.SubscriptionChargedSuccessfully)

    assert renewal.json() == {"status": "ok"}
    assert [tx for tx, _, _ in braintree_stub.issued] == ["sub1@2026-10-25", "sub1@2026-11-25"]


def test_webhook_rejects_bad_signature(client, monkeypatch, braintree_stub):
    def bad(signature, payload):
        raise HTTPException(status_code=400, detail="Invalid Braintree webhook signature.")

    monkeypatch.setattr(billing, "_parse_webhook", bad)

    response = client.post("/api/billing/braintree/webhook", data={"bt_signature": "sig", "bt_payload": "payload"})

    assert response.status_code == 400
    assert braintree_stub.issued == []


def test_webhook_requires_form_fields(client, braintree_stub):
    assert client.post("/api/billing/braintree/webhook", data={}).status_code == 400


def test_webhook_ignores_other_events(client, monkeypatch, braintree_stub):
    response = _webhook(client, monkeypatch, Kind.SubscriptionCanceled)

    assert response.json() == {"status": "ignored"}
    assert braintree_stub.issued == []


def test_webhook_acknowledges_unusable_subscription(client, monkeypatch, braintree_stub):
    monkeypatch.setattr(billing, "_get_subscription", lambda sub_id: _subscription(sub_id, status="Past Due"))

    assert _webhook(client, monkeypatch, Kind.SubscriptionWentActive).json() == {"status": "rejected"}


def test_webhook_signature_is_checked_by_braintree(monkeypatch):
    """The real parser, with a real sandbox-style config, rejects forged payloads."""
    monkeypatch.setattr(billing, "BRAINTREE_MERCHANT_ID", "merchant")
    monkeypatch.setattr(billing, "BRAINTREE_PUBLIC_KEY", "public")
    monkeypatch.setattr(billing, "BRAINTREE_PRIVATE_KEY", "private")
    monkeypatch.setattr(billing, "BRAINTREE_ENVIRONMENT", "sandbox")

    with pytest.raises(HTTPException) as exc:
        billing._parse_webhook("public|forged", "cGF5bG9hZA==")
    assert exc.value.status_code == 400
