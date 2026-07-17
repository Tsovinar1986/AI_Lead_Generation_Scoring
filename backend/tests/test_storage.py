from app import storage
from app.models import Alert

from .conftest import make_scored_lead

TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"


def test_upsert_dedupes_by_domain_not_id():
    storage.upsert_leads(TENANT, [make_scored_lead(domain="a.com", combined_score=50)])
    storage.upsert_leads(TENANT, [make_scored_lead(domain="a.com", combined_score=90)])

    leads = storage.list_leads(TENANT)
    assert len(leads) == 1
    assert leads[0].combined_score == 90


def test_list_leads_sorted_by_combined_score_desc():
    storage.upsert_leads(TENANT, [
        make_scored_lead(domain="low.com", combined_score=40),
        make_scored_lead(domain="high.com", combined_score=95),
        make_scored_lead(domain="mid.com", combined_score=70),
    ])

    domains = [lead.domain for lead in storage.list_leads(TENANT)]
    assert domains == ["high.com", "mid.com", "low.com"]


def test_get_lead_roundtrips_full_shape():
    lead = make_scored_lead(domain="acme.com")
    storage.upsert_leads(TENANT, [lead])

    fetched = storage.get_lead(TENANT, lead.id)
    assert fetched is not None
    assert fetched.company_name == lead.company_name
    assert fetched.score_breakdown.industry_match == lead.score_breakdown.industry_match


def test_get_lead_missing_returns_none():
    assert storage.get_lead(TENANT, "does-not-exist") is None


def test_alerts_returned_most_recent_first():
    storage.add_alert(TENANT, Alert(lead_id="1", company_name="First", combined_score=80, message="first"))
    storage.add_alert(TENANT, Alert(lead_id="2", company_name="Second", combined_score=90, message="second"))

    messages = [a.message for a in storage.list_alerts(TENANT)]
    assert messages == ["second", "first"]


def test_persists_across_reconnect(tmp_path):
    db_path = str(tmp_path / "persist.db")
    storage._reset_for_tests(db_path)
    storage.upsert_leads(TENANT, [make_scored_lead(domain="persist.com")])

    storage._conn.close()
    storage._conn = storage._connect()

    assert len(storage.list_leads(TENANT)) == 1


def test_clear_all_empties_both_tables():
    storage.upsert_leads(TENANT, [make_scored_lead()])
    storage.add_alert(TENANT, Alert(lead_id="1", company_name="X", combined_score=80, message="m"))

    storage.clear_all(TENANT)

    assert storage.list_leads(TENANT) == []
    assert storage.list_alerts(TENANT) == []


def test_leads_isolated_between_tenants():
    storage.upsert_leads(TENANT, [make_scored_lead(domain="a.com")])
    storage.upsert_leads(OTHER_TENANT, [make_scored_lead(domain="b.com")])

    assert [lead.domain for lead in storage.list_leads(TENANT)] == ["a.com"]
    assert [lead.domain for lead in storage.list_leads(OTHER_TENANT)] == ["b.com"]


def test_same_domain_in_two_tenants_does_not_collide():
    storage.upsert_leads(TENANT, [make_scored_lead(domain="shared.com", combined_score=10)])
    storage.upsert_leads(OTHER_TENANT, [make_scored_lead(domain="shared.com", combined_score=99)])

    assert storage.list_leads(TENANT)[0].combined_score == 10
    assert storage.list_leads(OTHER_TENANT)[0].combined_score == 99


def test_get_lead_cannot_cross_tenant_boundary():
    lead = make_scored_lead(domain="secret.com")
    storage.upsert_leads(TENANT, [lead])

    assert storage.get_lead(OTHER_TENANT, lead.id) is None
    assert storage.get_lead(TENANT, lead.id) is not None


def test_alerts_isolated_between_tenants():
    storage.add_alert(TENANT, Alert(lead_id="1", company_name="A", combined_score=80, message="mine"))
    storage.add_alert(OTHER_TENANT, Alert(lead_id="2", company_name="B", combined_score=80, message="theirs"))

    assert [a.message for a in storage.list_alerts(TENANT)] == ["mine"]
    assert [a.message for a in storage.list_alerts(OTHER_TENANT)] == ["theirs"]


def test_create_tenant_and_lookup_by_api_key():
    tenant, api_key = storage.create_tenant("Acme Corp")

    found = storage.get_tenant_by_api_key(api_key)
    assert found is not None
    assert found.id == tenant.id
    assert found.name == "Acme Corp"


def test_lookup_with_wrong_api_key_returns_none():
    storage.create_tenant("Acme Corp")
    assert storage.get_tenant_by_api_key("not-the-real-key") is None


def test_get_or_start_trial_is_stable_across_calls():
    first = storage.get_or_start_trial()
    second = storage.get_or_start_trial()
    assert first == second


def test_get_or_start_trial_persists_across_reconnect(tmp_path):
    db_path = str(tmp_path / "trial.db")
    storage._reset_for_tests(db_path)
    started = storage.get_or_start_trial()

    storage._conn.close()
    storage._conn = storage._connect()

    assert storage.get_or_start_trial() == started
