import json
import random

from ..config import (
    BUCKET_THRESHOLDS,
    ICP,
    LLM_WEIGHT,
    RULE_WEIGHT,
    SCORING_WEIGHTS,
)
from ..llm.client import get_client
from ..config import ANTHROPIC_MODEL
from ..models import EnrichedLead, ScoreBreakdown, ScoredLead


def _band_fit(value: int, low: int, high: int) -> float:
    """1.0 inside the band, decaying linearly to 0 the further outside it."""
    if value is None:
        return 0.5
    if low <= value <= high:
        return 1.0
    span = max(high - low, 1)
    distance = (low - value) if value < low else (value - high)
    return max(0.0, 1.0 - distance / span)


def _rule_score(lead: EnrichedLead) -> ScoreBreakdown:
    industry_match = 1.0 if lead.industry in ICP["target_industries"] else 0.25
    company_size_fit = _band_fit(lead.employee_count, *ICP["employee_range"])
    revenue_fit = _band_fit(lead.revenue_usd, *ICP["revenue_range_usd"])

    overlap = set(t.lower() for t in lead.tech_stack) & set(
        t.lower() for t in ICP["target_tech_stack"]
    )
    tech_stack_match = len(overlap) / len(ICP["target_tech_stack"])

    geography_fit = 1.0 if lead.geography in ICP["target_geographies"] else 0.2

    title = (lead.contact_title or "").lower()
    title_seniority = 1.0 if any(t in title for t in ICP["decision_maker_titles"]) else 0.3

    hiring_signal = 1.0 if lead.is_hiring else 0.0

    return ScoreBreakdown(
        industry_match=round(industry_match * SCORING_WEIGHTS["industry_match"], 1),
        company_size_fit=round(company_size_fit * SCORING_WEIGHTS["company_size_fit"], 1),
        revenue_fit=round(revenue_fit * SCORING_WEIGHTS["revenue_fit"], 1),
        tech_stack_match=round(tech_stack_match * SCORING_WEIGHTS["tech_stack_match"], 1),
        geography_fit=round(geography_fit * SCORING_WEIGHTS["geography_fit"], 1),
        title_seniority=round(title_seniority * SCORING_WEIGHTS["title_seniority"], 1),
        hiring_signal=round(hiring_signal * SCORING_WEIGHTS["hiring_signal"], 1),
    )


def _mock_llm_assessment(lead: EnrichedLead, fit_score: float) -> tuple[float, str]:
    rng = random.Random(hash(lead.domain) & 0xFFFFFFFF)
    jitter = rng.uniform(-8, 8)
    likelihood = max(0.0, min(100.0, fit_score + jitter))

    signals = []
    if lead.is_hiring:
        signals.append("active hiring activity")
    if lead.industry in ICP["target_industries"]:
        signals.append(f"industry fit ({lead.industry})")
    overlap = set(t.lower() for t in lead.tech_stack) & set(
        t.lower() for t in ICP["target_tech_stack"]
    )
    if overlap:
        signals.append(f"tech stack overlap ({', '.join(sorted(overlap))})")
    signal_text = "; ".join(signals) if signals else "no strong qualitative signals detected"

    rationale = (
        f"[mock LLM] Estimated conversion likelihood {likelihood:.0f}/100 for "
        f"{lead.company_name}, based on {signal_text}. Set ANTHROPIC_API_KEY to "
        f"replace this with a real Claude assessment."
    )
    return likelihood, rationale


def _llm_assessment(lead: EnrichedLead, fit_score: float, breakdown: ScoreBreakdown) -> tuple[float, str]:
    client = get_client()
    if client is None:
        return _mock_llm_assessment(lead, fit_score)

    prompt = f"""You are a B2B sales qualification assistant. Given this enriched lead
and its rule-based fit breakdown, assess conversion likelihood.

Lead:
- Company: {lead.company_name}
- Industry: {lead.industry}
- Employees: {lead.employee_count}
- Revenue (USD): {lead.revenue_usd}
- Geography: {lead.geography}
- Contact: {lead.contact_name} ({lead.contact_title})
- Tech stack: {", ".join(lead.tech_stack) or "unknown"}
- Currently hiring: {lead.is_hiring}

Rule-based fit_score: {fit_score:.1f}/100
Breakdown: {breakdown.model_dump()}

Respond with ONLY a JSON object of the form:
{{"conversion_likelihood": <0-100 number>, "rationale": "<one or two sentence rationale>"}}
"""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        data = json.loads(text.strip().strip("`"))
        return float(data["conversion_likelihood"]), str(data["rationale"])
    except Exception as exc:  # noqa: BLE001 - fall back rather than break scoring
        likelihood, rationale = _mock_llm_assessment(lead, fit_score)
        return likelihood, f"{rationale} (LLM call failed: {exc})"


def _bucket_for(score: float) -> str:
    if score >= BUCKET_THRESHOLDS["hot"]:
        return "hot"
    if score >= BUCKET_THRESHOLDS["warm"]:
        return "warm"
    return "cold"


def score_lead(lead: EnrichedLead) -> ScoredLead:
    breakdown = _rule_score(lead)
    fit_score = round(sum(breakdown.model_dump().values()), 1)

    conversion_likelihood, rationale = _llm_assessment(lead, fit_score, breakdown)

    combined_score = round(RULE_WEIGHT * fit_score + LLM_WEIGHT * conversion_likelihood, 1)
    bucket = _bucket_for(combined_score)

    return ScoredLead(
        **lead.model_dump(),
        fit_score=fit_score,
        score_breakdown=breakdown,
        conversion_likelihood=round(conversion_likelihood, 1),
        llm_rationale=rationale,
        combined_score=combined_score,
        bucket=bucket,
    )
