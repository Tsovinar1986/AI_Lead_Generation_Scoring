from unittest.mock import MagicMock

from app import storage
from app.routers import accounts


def _signup(client, email="buyer@acme.com", password="Correct-Horse9", name="Acme Corp"):
    return client.post("/api/accounts/signup", json={"name": name, "email": email, "password": password})


def test_signup_creates_a_usable_tenant(client):
    resp = _signup(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Acme Corp"
    assert body["api_key"]

    # The returned key actually works against a real endpoint.
    leads_resp = client.get("/api/leads", headers={"Authorization": f"Bearer {body['api_key']}"})
    assert leads_resp.status_code == 200


def test_signup_rejects_duplicate_email(client):
    _signup(client)
    resp = _signup(client, name="Someone Else")
    assert resp.status_code == 409


def test_signup_rejects_weak_password(client):
    resp = _signup(client, password="weak")
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


def test_signup_rejects_invalid_email(client):
    resp = client.post(
        "/api/accounts/signup", json={"name": "Acme", "email": "not-an-email", "password": "Correct-Horse9"}
    )
    assert resp.status_code == 422


def test_login_with_correct_credentials_succeeds(client):
    _signup(client)
    resp = client.post(
        "/api/accounts/login", json={"email": "buyer@acme.com", "password": "Correct-Horse9"}
    )
    assert resp.status_code == 200
    assert resp.json()["api_key"]


def test_login_with_wrong_password_fails(client):
    _signup(client)
    resp = client.post(
        "/api/accounts/login", json={"email": "buyer@acme.com", "password": "wrong-password9!"}
    )
    assert resp.status_code == 401


def test_login_with_unknown_email_fails(client):
    resp = client.post(
        "/api/accounts/login", json={"email": "nobody@nowhere.com", "password": "Correct-Horse9"}
    )
    assert resp.status_code == 401


def test_login_rotates_the_api_key(client):
    signup_resp = _signup(client)
    old_key = signup_resp.json()["api_key"]

    login_resp = client.post(
        "/api/accounts/login", json={"email": "buyer@acme.com", "password": "Correct-Horse9"}
    )
    new_key = login_resp.json()["api_key"]

    assert new_key != old_key
    assert client.get("/api/leads", headers={"Authorization": f"Bearer {old_key}"}).status_code == 401
    assert client.get("/api/leads", headers={"Authorization": f"Bearer {new_key}"}).status_code == 200


def test_forgot_password_gives_same_response_for_known_and_unknown_email(client):
    _signup(client)
    known = client.post("/api/accounts/forgot-password", json={"email": "buyer@acme.com"})
    unknown = client.post("/api/accounts/forgot-password", json={"email": "nobody@nowhere.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json()


def test_forgot_password_sends_email_when_account_exists(client, monkeypatch):
    _signup(client)
    send_mock = MagicMock(return_value=True)
    monkeypatch.setattr(accounts, "send_password_reset_email", send_mock)

    client.post("/api/accounts/forgot-password", json={"email": "buyer@acme.com"})

    assert send_mock.called
    to_email, reset_url, ttl_minutes = send_mock.call_args[0]
    assert to_email == "buyer@acme.com"
    assert "/reset-password?token=" in reset_url


def test_forgot_password_does_not_send_email_for_unknown_account(client, monkeypatch):
    send_mock = MagicMock(return_value=True)
    monkeypatch.setattr(accounts, "send_password_reset_email", send_mock)

    client.post("/api/accounts/forgot-password", json={"email": "nobody@nowhere.com"})

    assert not send_mock.called


def test_reset_password_with_valid_token_succeeds_and_new_password_works(client):
    _signup(client)
    tenant = storage.get_tenant_by_email("buyer@acme.com")
    token = storage.create_password_reset(tenant.id, ttl_seconds=3600)

    resp = client.post(
        "/api/accounts/reset-password", json={"token": token, "password": "New-Correct9"}
    )
    assert resp.status_code == 200

    login_resp = client.post(
        "/api/accounts/login", json={"email": "buyer@acme.com", "password": "New-Correct9"}
    )
    assert login_resp.status_code == 200

    old_login = client.post(
        "/api/accounts/login", json={"email": "buyer@acme.com", "password": "Correct-Horse9"}
    )
    assert old_login.status_code == 401


def test_reset_password_token_is_single_use(client):
    _signup(client)
    tenant = storage.get_tenant_by_email("buyer@acme.com")
    token = storage.create_password_reset(tenant.id, ttl_seconds=3600)

    first = client.post("/api/accounts/reset-password", json={"token": token, "password": "New-Correct9"})
    second = client.post("/api/accounts/reset-password", json={"token": token, "password": "Another-Correct9"})

    assert first.status_code == 200
    assert second.status_code == 400


def test_reset_password_rejects_invalid_token(client):
    resp = client.post(
        "/api/accounts/reset-password", json={"token": "not-a-real-token", "password": "New-Correct9"}
    )
    assert resp.status_code == 400


def test_reset_password_rejects_weak_new_password(client):
    _signup(client)
    tenant = storage.get_tenant_by_email("buyer@acme.com")
    token = storage.create_password_reset(tenant.id, ttl_seconds=3600)

    resp = client.post("/api/accounts/reset-password", json={"token": token, "password": "weak"})
    assert resp.status_code == 400
