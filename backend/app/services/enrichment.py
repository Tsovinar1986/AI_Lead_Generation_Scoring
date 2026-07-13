"""Firmographic + website enrichment.

Calls the Apollo.io organization-enrichment API when APOLLO_API_KEY is
configured. With no key set (the default), falls back to deterministic
pseudo-random data (seeded by domain) so results are stable across runs and
the rest of the pipeline can be built and tested without external accounts.
Any live-call failure (bad key, rate limit, network error, unknown domain)
also falls back to the mock rather than breaking the pipeline.
"""

import hashlib
import random

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import APOLLO_API_KEY, ICP
from ..models import EnrichedLead, Lead

_INDUSTRIES = ICP["target_industries"] + ["Manufacturing", "Retail", "Logistics", "Media"]
_GEOS = ICP["target_geographies"] + ["Germany", "Australia", "India"]
_TECH_POOL = ICP["target_tech_stack"] + [
    "GCP", "Azure", "Segment", "Zendesk", "Marketo", "Postgres", "Kafka",
]

APOLLO_ORG_ENRICH_URL = "https://api.apollo.io/api/v1/organizations/enrich"


def _rng_for(domain: str) -> random.Random:
    seed = int(hashlib.sha256(domain.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _mock_enrich(lead: Lead) -> EnrichedLead:
    rng = _rng_for(lead.domain)

    industry = lead.industry or rng.choice(_INDUSTRIES)
    employee_count = lead.employee_count or rng.randint(10, 5000)
    revenue_usd = lead.revenue_usd or employee_count * rng.randint(80_000, 250_000)
    geography = lead.geography or rng.choice(_GEOS)
    contact_title = lead.contact_title or rng.choice(
        ["VP of Sales", "Director of Ops", "CTO", "Marketing Manager", "Head of Growth"]
    )

    tech_stack = sorted(rng.sample(_TECH_POOL, k=rng.randint(1, 4)))
    is_hiring = rng.random() < 0.4

    return EnrichedLead(
        **{
            **lead.model_dump(),
            "industry": industry,
            "employee_count": employee_count,
            "revenue_usd": revenue_usd,
            "geography": geography,
            "contact_title": contact_title,
        },
        tech_stack=tech_stack,
        is_hiring=is_hiring,
        enrichment_source="mock",
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _fetch_apollo_org(domain: str) -> dict:
    response = requests.get(
        APOLLO_ORG_ENRICH_URL,
        params={"domain": domain},
        headers={"X-Api-Key": APOLLO_API_KEY, "Cache-Control": "no-cache"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _apollo_enrich(lead: Lead) -> EnrichedLead:
    data = _fetch_apollo_org(lead.domain)
    org = data.get("organization") or {}
    if not org:
        raise ValueError(f"Apollo returned no organization for domain {lead.domain}")

    keywords = [str(k) for k in (org.get("technology_names") or [])]

    fallback = _mock_enrich(lead)

    return EnrichedLead(
        **{
            **lead.model_dump(),
            "industry": lead.industry or org.get("industry") or fallback.industry,
            "employee_count": lead.employee_count or org.get("estimated_num_employees") or fallback.employee_count,
            "revenue_usd": lead.revenue_usd or org.get("annual_revenue") or fallback.revenue_usd,
            "geography": lead.geography or org.get("country") or fallback.geography,
            "contact_title": lead.contact_title,
        },
        tech_stack=sorted(keywords)[:6] if keywords else fallback.tech_stack,
        is_hiring=(org.get("job_postings_count") or 0) > 0,
        enrichment_source="apollo",
    )


def enrich_lead(lead: Lead) -> EnrichedLead:
    if not APOLLO_API_KEY:
        return _mock_enrich(lead)

    try:
        return _apollo_enrich(lead)
    except Exception as exc:  # noqa: BLE001 - fall back rather than break the pipeline
        logger.warning("Apollo enrichment failed for {}: {} — falling back to mock", lead.domain, exc)
        return _mock_enrich(lead)
