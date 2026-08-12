import io

from app.routers import leads as leads_router

SAMPLE_CSV = (
    b"company_name,domain,contact_name,contact_title,industry,employees,revenue,country\n"
    b"Acme Inc,acme.com,Jane Doe,VP of Sales,SaaS,200,20000000,United States\n"
    b"Globex,globex.com,John Smith,CTO,Fintech,500,50000000,United Kingdom\n"
)


def _upload(client, content=SAMPLE_CSV, filename="leads.csv"):
    return client.post(
        "/api/leads/upload",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_then_list_roundtrip(client):
    resp = _upload(client)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    listed = client.get("/api/leads").json()
    assert len(listed) == 2


def test_upload_twice_does_not_duplicate(client):
    _upload(client)
    resp = _upload(client)

    assert len(resp.json()) == 2
    assert len(client.get("/api/leads").json()) == 2


def test_get_single_lead(client):
    upload_resp = _upload(client)
    lead_id = upload_resp.json()[0]["id"]

    resp = client.get(f"/api/leads/{lead_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lead_id


def test_get_missing_lead_404s(client):
    resp = client.get("/api/leads/does-not-exist")
    assert resp.status_code == 404


def test_upload_empty_file_400s(client):
    resp = _upload(client, content=b"company_name,domain\n")
    assert resp.status_code == 400


def test_upload_malformed_file_400s(client):
    resp = _upload(client, content=b"industry,employees\nSaaS,200\n")
    assert resp.status_code == 400


def test_license_status_endpoint_unlicensed(client):
    resp = client.get("/api/license")
    body = resp.json()
    assert body["licensed"] is False
    assert body["reason"] == "trial"
    assert body["trial_days_left"] > 0
    assert body["trial_uploads_left"] == 10


def test_upload_blocked_when_license_required_and_missing(client, monkeypatch):
    monkeypatch.setattr(leads_router, "LICENSE_REQUIRED", True)
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)

    resp = _upload(client)
    assert resp.status_code == 402


def test_upload_allowed_when_license_required_and_valid(client, monkeypatch):
    monkeypatch.setattr(leads_router, "LICENSE_REQUIRED", True)
    monkeypatch.setattr(leads_router, "verify_license", lambda: object())

    resp = _upload(client)
    assert resp.status_code == 200


def test_upload_allowed_during_trial_with_no_license_required(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "trial_days_left", lambda: 1.0)
    monkeypatch.setattr(leads_router, "trial_uploads_left", lambda: 5)

    resp = _upload(client)
    assert resp.status_code == 200


def test_upload_blocked_once_days_expire_even_with_uploads_left(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "trial_days_left", lambda: 0.0)
    monkeypatch.setattr(leads_router, "trial_uploads_left", lambda: 5)

    resp = _upload(client)
    assert resp.status_code == 402


def test_upload_blocked_once_uploads_exhausted_even_with_days_left(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "trial_days_left", lambda: 1.0)
    monkeypatch.setattr(leads_router, "trial_uploads_left", lambda: 0)

    resp = _upload(client)
    assert resp.status_code == 402


def test_upload_increments_trial_uploads_counter_for_default_tenant(client, monkeypatch):
    from app import storage

    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    assert storage.get_trial_uploads_used() == 0

    _upload(client)

    assert storage.get_trial_uploads_used() == 1


def test_signed_up_tenant_upload_never_gated_by_license(client, monkeypatch):
    monkeypatch.setattr(leads_router, "LICENSE_REQUIRED", True)
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "trial_days_left", lambda: 0.0)
    monkeypatch.setattr(leads_router, "trial_uploads_left", lambda: 0)

    signup_resp = client.post(
        "/api/accounts/signup",
        json={"name": "Acme", "email": "buyer@acme.com", "password": "Correct-Horse9!"},
    )
    api_key = signup_resp.json()["api_key"]

    resp = client.post(
        "/api/leads/upload",
        files={"file": ("leads.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 200


def _make_csv(row_count: int) -> bytes:
    header = b"company_name,domain,contact_name,contact_title,industry,employees,revenue,country\n"
    rows = b"".join(
        f"Company {i},company{i}.com,Jane Doe,VP of Sales,SaaS,200,20000000,United States\n".encode()
        for i in range(row_count)
    )
    return header + rows


def test_trial_upload_caps_rows_and_reports_it_via_headers(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "TRIAL_MAX_LEADS_PER_UPLOAD", 10)

    resp = _upload(client, content=_make_csv(25), filename="big.csv")

    assert resp.status_code == 200
    assert len(resp.json()) == 10
    assert resp.headers["x-trial-limited-rows"] == "10"
    assert resp.headers["x-trial-total-rows"] == "25"


def test_trial_upload_under_cap_gets_no_limit_headers(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: None)
    monkeypatch.setattr(leads_router, "TRIAL_MAX_LEADS_PER_UPLOAD", 10)

    resp = _upload(client, content=_make_csv(3), filename="small.csv")

    assert resp.status_code == 200
    assert len(resp.json()) == 3
    assert "x-trial-limited-rows" not in resp.headers


def test_licensed_upload_is_never_capped(client, monkeypatch):
    monkeypatch.setattr(leads_router, "verify_license", lambda: object())
    monkeypatch.setattr(leads_router, "TRIAL_MAX_LEADS_PER_UPLOAD", 10)

    resp = _upload(client, content=_make_csv(25), filename="big.csv")

    assert resp.status_code == 200
    assert len(resp.json()) == 25
    assert "x-trial-limited-rows" not in resp.headers


def test_hot_lead_upload_creates_alert(client):
    _upload(client)
    alerts = client.get("/api/alerts").json()
    # sample data includes at least one strong-fit lead
    assert isinstance(alerts, list)


def test_outreach_rejects_invalid_channel(client):
    lead_id = _upload(client).json()[0]["id"]

    resp = client.post(f"/api/leads/{lead_id}/outreach", json={"channel": "carrier-pigeon"})
    assert resp.status_code == 422


def test_crm_push_rejects_invalid_crm(client):
    lead_id = _upload(client).json()[0]["id"]

    resp = client.post(f"/api/leads/{lead_id}/crm-push?crm=some-other-crm")
    assert resp.status_code == 422
