from app import storage
from app.models import Alert

from .conftest import make_scored_lead


def test_upsert_dedupes_by_domain_not_id():
    storage.upsert_leads([make_scored_lead(domain="a.com", combined_score=50)])
    storage.upsert_leads([make_scored_lead(domain="a.com", combined_score=90)])

    leads = storage.list_leads()
    assert len(leads) == 1
    assert leads[0].combined_score == 90


def test_list_leads_sorted_by_combined_score_desc():
    storage.upsert_leads([
        make_scored_lead(domain="low.com", combined_score=40),
        make_scored_lead(domain="high.com", combined_score=95),
        make_scored_lead(domain="mid.com", combined_score=70),
    ])

    domains = [lead.domain for lead in storage.list_leads()]
    assert domains == ["high.com", "mid.com", "low.com"]


def test_get_lead_roundtrips_full_shape():
    lead = make_scored_lead(domain="acme.com")
    storage.upsert_leads([lead])

    fetched = storage.get_lead(lead.id)
    assert fetched is not None
    assert fetched.company_name == lead.company_name
    assert fetched.score_breakdown.industry_match == lead.score_breakdown.industry_match


def test_get_lead_missing_returns_none():
    assert storage.get_lead("does-not-exist") is None


def test_alerts_returned_most_recent_first():
    storage.add_alert(Alert(lead_id="1", company_name="First", combined_score=80, message="first"))
    storage.add_alert(Alert(lead_id="2", company_name="Second", combined_score=90, message="second"))

    messages = [a.message for a in storage.list_alerts()]
    assert messages == ["second", "first"]


def test_persists_across_reconnect(tmp_path):
    db_path = str(tmp_path / "persist.db")
    storage._reset_for_tests(db_path)
    storage.upsert_leads([make_scored_lead(domain="persist.com")])

    storage._conn.close()
    storage._conn = storage._connect()

    assert len(storage.list_leads()) == 1


def test_clear_all_empties_both_tables():
    storage.upsert_leads([make_scored_lead()])
    storage.add_alert(Alert(lead_id="1", company_name="X", combined_score=80, message="m"))

    storage.clear_all()

    assert storage.list_leads() == []
    assert storage.list_alerts() == []
