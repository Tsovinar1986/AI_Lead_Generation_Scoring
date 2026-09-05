import base64
import hashlib
import hmac
import json
import time

from app.routers import billing


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_body = json_body or {}
        self.text = text or json.dumps(self._json_body)

    def json(self):
        return self._json_body


def _sign(ts: int, raw_body: bytes, secret: str) -> str:
    signed_payload = f"{ts}:{raw_body.decode()}"
    h1 = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def _event(event_type: str, data: dict, secret: str = "pdl_ntfset_test") -> tuple[bytes, str]:
    raw_body = json.dumps({"event_type": event_type, "data": data}).encode()
    return raw_body, _sign(int(time.time()), raw_body, secret)


def _decode_license_payload(license_key: str) -> dict:
    payload_b64 = license_key.split(".", 1)[0]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


_POLAR_TEST_SECRET = "whsec_" + base64.b64encode(b"polar-test-secret-bytes").decode()


def _polar_sign(webhook_id: str, ts: int, raw_body: bytes, secret: str) -> str:
    secret_bytes = base64.b64decode(secret[len("whsec_"):])
    signed_content = f"{webhook_id}.{ts}.{raw_body.decode()}"
    sig = base64.b64encode(hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()).decode()
    return f"v1,{sig}"


def _polar_event(event_type: str, data: dict, secret: str = _POLAR_TEST_SECRET, webhook_id: str = "msg_test"):
    raw_body = json.dumps({"type": event_type, "data": data}).encode()
    ts = int(time.time())
    sig = _polar_sign(webhook_id, ts, raw_body, secret)
    headers = {"webhook-id": webhook_id, "webhook-timestamp": str(ts), "webhook-signature": sig}
    return raw_body, headers


def test_billing_config_exposes_non_secret_checkout_settings(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_CLIENT_TOKEN", "live_abc123")
    monkeypatch.setattr(billing, "PADDLE_ENVIRONMENT", "sandbox")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_MONTHLY", "pri_monthly")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ANNUAL", "pri_annual")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ADVANCED_MONTHLY", "pri_advanced_monthly")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ADVANCED_ANNUAL", "pri_advanced_annual")
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "")

    resp = client.get("/api/billing/config")
    assert resp.status_code == 200
    assert resp.json() == {
        "client_token": "live_abc123",
        "environment": "sandbox",
        "price_id_monthly": "pri_monthly",
        "price_id_annual": "pri_annual",
        "price_id_advanced_monthly": "pri_advanced_monthly",
        "price_id_advanced_annual": "pri_advanced_annual",
        "polar_available": False,
    }


def test_billing_config_reports_polar_available_only_when_fully_configured(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_MONTHLY", "prod_monthly")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_ANNUAL", "")

    resp = client.get("/api/billing/config")
    assert resp.json()["polar_available"] is False

    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_ANNUAL", "prod_annual")
    resp = client.get("/api/billing/config")
    assert resp.json()["polar_available"] is True


def test_billing_config_reports_unset_values_as_null(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_CLIENT_TOKEN", "")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_MONTHLY", "")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ANNUAL", "")

    resp = client.get("/api/billing/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["client_token"] is None
    assert body["price_id_monthly"] is None
    assert body["price_id_annual"] is None


def test_webhook_without_secret_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "")

    resp = client.post("/api/billing/webhook", content=b"{}", headers={"paddle-signature": "ts=1;h1=bad"})
    assert resp.status_code == 503


def test_webhook_rejects_tampered_signature(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")

    resp = client.post(
        "/api/billing/webhook",
        content=b'{"event_type":"transaction.completed"}',
        headers={"paddle-signature": f"ts={int(time.time())};h1=deadbeef"},
    )
    assert resp.status_code == 400


def test_webhook_rejects_stale_timestamp(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    raw_body = b'{"event_type":"transaction.completed","data":{}}'
    stale_ts = int(time.time()) - 10_000
    sig = _sign(stale_ts, raw_body, "pdl_ntfset_test")

    resp = client.post("/api/billing/webhook", content=raw_body, headers={"paddle-signature": sig})
    assert resp.status_code == 400


def test_webhook_rejects_missing_signature_header(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")

    resp = client.post("/api/billing/webhook", content=b"{}", headers={})
    assert resp.status_code == 400


def test_transaction_completed_issues_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    monkeypatch.setattr(billing, "PADDLE_API_KEY", "pdl_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(
        billing.requests, "get", lambda *a, **k: FakeResponse(200, {"data": {"email": "buyer@example.com"}})
    )

    payload, sig = _event(
        "transaction.completed",
        {"customer_id": "ctm_123", "items": [{"price": {"id": "pri_monthly"}}]},
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["email"] == "buyer@example.com"


def test_transaction_completed_with_annual_price_issues_annual_validity(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    monkeypatch.setattr(billing, "PADDLE_API_KEY", "pdl_test")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ANNUAL", "pri_annual_123")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    monkeypatch.setattr(billing, "LICENSE_VALIDITY_DAYS_ANNUAL", 380)
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(
        billing.requests, "get", lambda *a, **k: FakeResponse(200, {"data": {"email": "buyer@example.com"}})
    )

    payload, sig = _event(
        "transaction.completed",
        {"customer_id": "ctm_123", "items": [{"price": {"id": "pri_annual_123"}}]},
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    license_key = json.loads(log_path.read_text().splitlines()[0])["license_key"]
    issued = _decode_license_payload(license_key)
    assert issued["plan"] == "annual"
    assert round((issued["expires_at"] - issued["issued_at"]) / 86400) == 380


def test_transaction_completed_without_customer_id_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("transaction.completed", {"items": [{"price": {"id": "pri_monthly"}}]})
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    assert not log_path.exists()


def test_transaction_completed_email_lookup_failure_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    monkeypatch.setattr(billing, "PADDLE_API_KEY", "pdl_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(billing.requests, "get", lambda *a, **k: FakeResponse(404, {}, "not found"))

    payload, sig = _event(
        "transaction.completed",
        {"customer_id": "ctm_missing", "items": [{"price": {"id": "pri_monthly"}}]},
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    assert not log_path.exists()


def test_subscription_canceled_issues_no_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("subscription.canceled", {"customer_id": "ctm_123"})
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    assert not log_path.exists()


def test_transaction_completed_retry_does_not_issue_a_second_license(client, monkeypatch, tmp_path):
    """Paddle delivers at-least-once -- a retried delivery for the same
    transaction_id must not mint (and email) a second license."""
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    monkeypatch.setattr(billing, "PADDLE_API_KEY", "pdl_test")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(
        billing.requests, "get", lambda *a, **k: FakeResponse(200, {"data": {"email": "buyer@example.com"}})
    )

    data = {"id": "txn_retry_1", "customer_id": "ctm_123", "items": [{"price": {"id": "pri_monthly"}}]}
    payload, sig = _event("transaction.completed", data)
    first = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})
    assert first.status_code == 200
    assert first.json()["status"] == "ok"

    # Same transaction, redelivered (Paddle retries on anything but a 2xx,
    # and can also just deliver twice) -- re-sign since the signature covers
    # a fresh timestamp, but the event body/transaction id is identical.
    payload2, sig2 = _event("transaction.completed", data)
    second = client.post("/api/billing/webhook", content=payload2, headers={"paddle-signature": sig2})
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    lines = log_path.read_text().splitlines()
    assert len(lines) == 1


def test_subscription_created_and_updated_are_logged_without_issuing_a_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event(
        "subscription.created",
        {"id": "sub_1", "customer_id": "ctm_123", "status": "trialing", "items": [{"price": {"id": "pri_monthly"}}]},
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert not log_path.exists()

    payload, sig = _event(
        "subscription.updated",
        {
            "id": "sub_1",
            "customer_id": "ctm_123",
            "status": "active",
            "scheduled_change": {"action": "cancel", "effective_at": "2027-01-01T00:00:00Z"},
        },
    )
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert not log_path.exists()


def test_customer_created_and_updated_are_logged_without_issuing_a_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    for event_type in ("customer.created", "customer.updated"):
        payload, sig = _event(event_type, {"id": "ctm_123", "email": "buyer@example.com"})
        resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    assert not log_path.exists()


def test_unknown_event_type_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "PADDLE_WEBHOOK_SECRET", "pdl_ntfset_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, sig = _event("some.future.event.paddle.adds.later", {"id": "whatever"})
    resp = client.post("/api/billing/webhook", content=payload, headers={"paddle-signature": sig})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert not log_path.exists()


# --- Polar ---


def test_polar_checkout_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "")

    resp = client.post("/api/billing/polar/checkout", json={"interval": "monthly"})
    assert resp.status_code == 503


def test_polar_checkout_rejects_invalid_interval(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")

    resp = client.post("/api/billing/polar/checkout", json={"interval": "biannual"})
    assert resp.status_code == 422


def test_polar_checkout_returns_session_url(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_MONTHLY", "prod_monthly")
    monkeypatch.setattr(billing, "POLAR_ENVIRONMENT", "sandbox")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse(200, {"url": "https://sandbox.polar.sh/checkout/abc123"})

    monkeypatch.setattr(billing.requests, "post", fake_post)

    resp = client.post("/api/billing/polar/checkout", json={"interval": "monthly"})
    assert resp.status_code == 200
    assert resp.json() == {"url": "https://sandbox.polar.sh/checkout/abc123"}
    assert captured["url"] == "https://sandbox-api.polar.sh/v1/checkouts/"
    assert captured["json"] == {"products": ["prod_monthly"]}


def test_polar_checkout_annual_uses_annual_product(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_ANNUAL", "prod_annual")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse(200, {"url": "https://sandbox.polar.sh/checkout/xyz"})

    monkeypatch.setattr(billing.requests, "post", fake_post)

    resp = client.post("/api/billing/polar/checkout", json={"interval": "annual"})
    assert resp.status_code == 200
    assert captured["json"] == {"products": ["prod_annual"]}


def test_polar_checkout_upstream_failure_returns_502(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_MONTHLY", "prod_monthly")
    monkeypatch.setattr(billing.requests, "post", lambda *a, **k: FakeResponse(422, {}, "invalid product"))

    resp = client.post("/api/billing/polar/checkout", json={"interval": "monthly"})
    assert resp.status_code == 502


def test_polar_webhook_without_secret_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", "")

    resp = client.post(
        "/api/billing/polar/webhook",
        content=b"{}",
        headers={"webhook-id": "msg_1", "webhook-timestamp": str(int(time.time())), "webhook-signature": "v1,bad"},
    )
    assert resp.status_code == 503


def test_polar_webhook_rejects_tampered_signature(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)

    resp = client.post(
        "/api/billing/polar/webhook",
        content=b'{"type":"order.paid","data":{}}',
        headers={
            "webhook-id": "msg_1",
            "webhook-timestamp": str(int(time.time())),
            "webhook-signature": "v1,deadbeef==",
        },
    )
    assert resp.status_code == 400


def test_polar_webhook_rejects_stale_timestamp(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    raw_body = b'{"type":"order.paid","data":{}}'
    stale_ts = int(time.time()) - 10_000
    sig = _polar_sign("msg_1", stale_ts, raw_body, _POLAR_TEST_SECRET)

    resp = client.post(
        "/api/billing/polar/webhook",
        content=raw_body,
        headers={"webhook-id": "msg_1", "webhook-timestamp": str(stale_ts), "webhook-signature": sig},
    )
    assert resp.status_code == 400


def test_polar_webhook_rejects_missing_headers(client, monkeypatch):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)

    resp = client.post("/api/billing/polar/webhook", content=b"{}", headers={})
    assert resp.status_code == 400


def test_polar_order_paid_issues_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_MONTHLY", "prod_monthly")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(billing.requests, "get", lambda *a, **k: FakeResponse(200, {"email": "buyer@example.com"}))

    payload, headers = _polar_event(
        "order.paid", {"customer_id": "cus_123", "product_id": "prod_monthly"}
    )
    resp = client.post("/api/billing/polar/webhook", content=payload, headers=headers)

    assert resp.status_code == 200
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["email"] == "buyer@example.com"


def test_polar_order_paid_with_annual_product_issues_annual_validity(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    monkeypatch.setattr(billing, "POLAR_PRODUCT_ID_ANNUAL", "prod_annual_123")
    monkeypatch.setattr(billing, "LICENSE_PRIVATE_KEY", "exqa9gnLag9xfbgoe_m4nVAxgpHw6H7b53OutEcHCmY")
    monkeypatch.setattr(billing, "LICENSE_VALIDITY_DAYS_ANNUAL", 380)
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(billing.requests, "get", lambda *a, **k: FakeResponse(200, {"email": "buyer@example.com"}))

    payload, headers = _polar_event(
        "order.paid", {"customer_id": "cus_123", "product_id": "prod_annual_123"}
    )
    resp = client.post("/api/billing/polar/webhook", content=payload, headers=headers)

    assert resp.status_code == 200
    license_key = json.loads(log_path.read_text().splitlines()[0])["license_key"]
    issued = _decode_license_payload(license_key)
    assert issued["plan"] == "annual"
    assert round((issued["expires_at"] - issued["issued_at"]) / 86400) == 380


def test_polar_order_paid_without_customer_id_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, headers = _polar_event("order.paid", {"product_id": "prod_monthly"})
    resp = client.post("/api/billing/polar/webhook", content=payload, headers=headers)

    assert resp.status_code == 200
    assert not log_path.exists()


def test_polar_order_paid_email_lookup_failure_is_ignored(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    monkeypatch.setattr(billing, "POLAR_ACCESS_TOKEN", "polar_oat_test")
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)
    monkeypatch.setattr(billing.requests, "get", lambda *a, **k: FakeResponse(404, {}, "not found"))

    payload, headers = _polar_event("order.paid", {"customer_id": "cus_missing", "product_id": "prod_monthly"})
    resp = client.post("/api/billing/polar/webhook", content=payload, headers=headers)

    assert resp.status_code == 200
    assert not log_path.exists()


def test_polar_subscription_canceled_issues_no_license(client, monkeypatch, tmp_path):
    monkeypatch.setattr(billing, "POLAR_WEBHOOK_SECRET", _POLAR_TEST_SECRET)
    log_path = tmp_path / "issued_licenses.jsonl"
    monkeypatch.setattr(billing, "_ISSUED_LICENSES_LOG", log_path)

    payload, headers = _polar_event("subscription.canceled", {"customer_id": "cus_123"})
    resp = client.post("/api/billing/polar/webhook", content=payload, headers=headers)

    assert resp.status_code == 200
    assert not log_path.exists()
