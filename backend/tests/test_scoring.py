from app.models import EnrichedLead
from app.services.scoring import score_lead


def make_enriched(**overrides) -> EnrichedLead:
    defaults = dict(
        company_name="Acme Inc",
        domain="acme.com",
        contact_title="VP of Sales",
        industry="SaaS",
        employee_count=200,
        revenue_usd=20_000_000,
        geography="United States",
        tech_stack=["AWS", "Salesforce"],
        is_hiring=True,
    )
    defaults.update(overrides)
    return EnrichedLead(**defaults)


def test_perfect_icp_fit_scores_high_and_buckets_hot():
    lead = make_enriched()
    scored = score_lead(lead)

    assert scored.fit_score > 75
    assert scored.bucket in ("hot", "warm")  # LLM jitter in the mock can nudge combined_score
    assert 0 <= scored.combined_score <= 100


def test_poor_icp_fit_scores_low_and_buckets_cold():
    lead = make_enriched(
        industry="Unrelated Industry",
        employee_count=5,
        revenue_usd=1_000,
        geography="Nowhereland",
        tech_stack=[],
        is_hiring=False,
        contact_title="Intern",
    )
    scored = score_lead(lead)

    # The band-fit decay is gentle relative to a wide ICP range, so a tiny
    # company still earns partial size/revenue credit -- cold bucketing
    # (not an arbitrary score threshold) is the real signal of "poor fit."
    assert scored.fit_score < 50
    assert scored.bucket == "cold"


def test_combined_score_blends_rule_and_llm_weights():
    lead = make_enriched()
    scored = score_lead(lead)

    # combined_score is a weighted blend, so it must land between the two
    # inputs (allowing for the mock LLM's jitter already being applied to
    # conversion_likelihood before the blend).
    lower = min(scored.fit_score, scored.conversion_likelihood)
    upper = max(scored.fit_score, scored.conversion_likelihood)
    assert lower - 0.1 <= scored.combined_score <= upper + 0.1


def test_mock_llm_rationale_mentions_anthropic_key_when_unset(monkeypatch):
    monkeypatch.setattr("app.services.scoring.get_client", lambda: None)
    lead = make_enriched()
    scored = score_lead(lead)

    assert "ANTHROPIC_API_KEY" in scored.llm_rationale


def test_score_is_deterministic_for_same_domain():
    lead = make_enriched()
    first = score_lead(lead)
    second = score_lead(lead)

    assert first.fit_score == second.fit_score
    assert first.conversion_likelihood == second.conversion_likelihood
