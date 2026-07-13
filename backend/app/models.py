import uuid
from typing import Optional

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Lead(BaseModel):
    """Raw lead as ingested from CSV/XLSX or a live CRM pull."""

    id: str = Field(default_factory=new_id)
    company_name: str
    domain: str
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_usd: Optional[int] = None
    geography: Optional[str] = None
    source: str = "csv_upload"


class EnrichedLead(Lead):
    """Lead after firmographic/website enrichment fills in missing fields."""

    tech_stack: list[str] = Field(default_factory=list)
    is_hiring: bool = False
    enrichment_source: str = "mock"


class ScoreBreakdown(BaseModel):
    industry_match: float
    company_size_fit: float
    revenue_fit: float
    tech_stack_match: float
    geography_fit: float
    title_seniority: float
    hiring_signal: float


class ScoredLead(EnrichedLead):
    fit_score: float
    score_breakdown: ScoreBreakdown
    conversion_likelihood: float
    llm_rationale: str
    combined_score: float
    bucket: str  # "hot" | "warm" | "cold"
    outreach_draft: Optional[str] = None
    crm_pushed: bool = False


class OutreachRequest(BaseModel):
    channel: str = "email"  # "email" | "linkedin"


class OutreachResponse(BaseModel):
    lead_id: str
    channel: str
    draft: str


class CrmPushResponse(BaseModel):
    lead_id: str
    crm: str
    status: str
    detail: str


class Alert(BaseModel):
    id: str = Field(default_factory=new_id)
    lead_id: str
    company_name: str
    combined_score: float
    message: str
    channel: str = "slack"
