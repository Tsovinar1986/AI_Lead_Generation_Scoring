"""End-to-end tenant isolation and auth, exercised through the real HTTP API
(not storage.py directly) -- this is what actually protects a seller's
shared multi-tenant deployment from one customer seeing another's leads.
"""

import io

from app import storage

SAMPLE_CSV = b"company_name,domain\nAcme Inc,acme.com\n"


def _upload(client, headers=None):
    return client.post(
        "/api/leads/upload",
        files={"file": ("leads.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers or {},
    )


def test_no_auth_header_uses_default_tenant(client):
    resp = _upload(client)
    assert resp.status_code == 200

    listed = client.get("/api/leads").json()
    assert len(listed) == 1


def test_invalid_bearer_token_rejected(client):
    resp = _upload(client, headers={"Authorization": "Bearer not-a-real-key"})
    assert resp.status_code == 401


def test_malformed_authorization_header_rejected(client):
    resp = _upload(client, headers={"Authorization": "not-bearer-format"})
    assert resp.status_code == 401


def test_two_tenants_do_not_see_each_others_leads(client):
    _, key_a = storage.create_tenant("Tenant A")
    _, key_b = storage.create_tenant("Tenant B")

    _upload(client, headers={"Authorization": f"Bearer {key_a}"})

    leads_a = client.get("/api/leads", headers={"Authorization": f"Bearer {key_a}"}).json()
    leads_b = client.get("/api/leads", headers={"Authorization": f"Bearer {key_b}"}).json()

    assert len(leads_a) == 1
    assert len(leads_b) == 0


def test_tenant_cannot_fetch_another_tenants_lead_by_id(client):
    _, key_a = storage.create_tenant("Tenant A")
    _, key_b = storage.create_tenant("Tenant B")

    upload_resp = _upload(client, headers={"Authorization": f"Bearer {key_a}"})
    lead_id = upload_resp.json()[0]["id"]

    resp = client.get(f"/api/leads/{lead_id}", headers={"Authorization": f"Bearer {key_b}"})
    assert resp.status_code == 404


def test_default_tenant_isolated_from_provisioned_tenant(client):
    _, key_a = storage.create_tenant("Tenant A")

    _upload(client)  # no auth header -> default tenant
    _upload(client, headers={"Authorization": f"Bearer {key_a}"})

    default_leads = client.get("/api/leads").json()
    tenant_a_leads = client.get("/api/leads", headers={"Authorization": f"Bearer {key_a}"}).json()

    assert len(default_leads) == 1
    assert len(tenant_a_leads) == 1


def test_alerts_isolated_between_tenants(client):
    hot_csv = (
        b"company_name,domain,industry,employees,revenue,country\n"
        b"Fintura Pay,finturapay.com,Fintech,210,28000000,United States\n"
    )
    _, key_a = storage.create_tenant("Tenant A")
    _, key_b = storage.create_tenant("Tenant B")

    _upload_with_content(client, hot_csv, headers={"Authorization": f"Bearer {key_a}"})

    alerts_a = client.get("/api/alerts", headers={"Authorization": f"Bearer {key_a}"}).json()
    alerts_b = client.get("/api/alerts", headers={"Authorization": f"Bearer {key_b}"}).json()

    assert isinstance(alerts_a, list)
    assert alerts_b == []


def _upload_with_content(client, content, headers):
    return client.post(
        "/api/leads/upload",
        files={"file": ("leads.csv", io.BytesIO(content), "text/csv")},
        headers=headers,
    )
