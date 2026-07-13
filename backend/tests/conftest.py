import pytest

from app import storage
from app.models import ScoreBreakdown, ScoredLead


@pytest.fixture(autouse=True)
def fresh_storage(tmp_path):
    """Every test gets its own SQLite file so tests never see each other's
    leads/alerts -- storage.py is a real DB now, not an in-memory dict that
    resets itself between test processes.
    """
    storage._reset_for_tests(str(tmp_path / "test.db"))
    yield
    storage._conn.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def make_scored_lead(**overrides) -> ScoredLead:
    defaults = dict(
        company_name="Acme Inc",
        domain="acme.com",
        contact_name="Jane Doe",
        contact_title="VP of Sales",
        industry="SaaS",
        employee_count=200,
        revenue_usd=20_000_000,
        geography="United States",
        tech_stack=["AWS", "Salesforce"],
        is_hiring=True,
        fit_score=80.0,
        score_breakdown=ScoreBreakdown(
            industry_match=20, company_size_fit=20, revenue_fit=15,
            tech_stack_match=15, geography_fit=10, title_seniority=10, hiring_signal=10,
        ),
        conversion_likelihood=80.0,
        llm_rationale="strong fit",
        combined_score=80.0,
        bucket="hot",
    )
    defaults.update(overrides)
    return ScoredLead(**defaults)
