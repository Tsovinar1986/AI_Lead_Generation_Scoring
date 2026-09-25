from app.routers import billing


def test_billing_config_exposes_paypal_settings(client, monkeypatch):
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_ID", "client")
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setattr(billing, "PAYPAL_PRICE_MONTHLY", "20.00")
    monkeypatch.setattr(billing, "PAYPAL_PRICE_ANNUAL", "192.00")
    monkeypatch.setattr(billing, "PAYPAL_PRICE_ADVANCED_MONTHLY", "40.00")
    monkeypatch.setattr(billing, "PAYPAL_PRICE_ADVANCED_ANNUAL", "384.00")

    response = client.get("/api/billing/config")

    assert response.status_code == 200
    assert response.json()["paypal_available"] is True
    assert response.json()["currency"] == "USD"


def test_checkout_requires_paypal_pricing(client, monkeypatch):
    monkeypatch.setattr(billing, "PAYPAL_PRICE_MONTHLY", "")
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_ID", "client")
    monkeypatch.setattr(billing, "PAYPAL_CLIENT_SECRET", "secret")

    response = client.post("/api/billing/paypal/checkout", json={"interval": "monthly", "tier": "pro"})

    assert response.status_code == 503
