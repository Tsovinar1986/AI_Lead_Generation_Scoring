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


def test_billing_config_exposes_non_secret_checkout_settings(client, monkeypatch):
    monkeypatch.setattr(billing, "PADDLE_CLIENT_TOKEN", "live_abc123")
    monkeypatch.setattr(billing, "PADDLE_ENVIRONMENT", "sandbox")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_MONTHLY", "pri_monthly")
    monkeypatch.setattr(billing, "PADDLE_PRICE_ID_ANNUAL", "pri_annual")

    resp = client.get("/api/billing/config")
    assert resp.status_code == 200
    assert resp.json() == {
        "client_token": "live_abc123",
        "environment": "sandbox",
        "price_id_monthly": "pri_monthly",
        "price_id_annual": "pri_annual",
    }


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
