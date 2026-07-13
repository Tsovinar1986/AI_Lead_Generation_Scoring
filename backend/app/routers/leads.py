from fastapi import APIRouter, Depends, HTTPException, UploadFile

from .. import storage
from ..auth import get_current_tenant
from ..config import LICENSE_REQUIRED
from ..licensing import verify_license
from ..models import ScoredLead
from ..services.alerts import maybe_alert
from ..services.enrichment import enrich_lead
from ..services.ingestion import parse_leads_file
from ..services.scoring import score_lead

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("/upload", response_model=list[ScoredLead])
async def upload_leads(file: UploadFile, tenant: storage.Tenant = Depends(get_current_tenant)):
    if LICENSE_REQUIRED and verify_license() is None:
        raise HTTPException(
            status_code=402,
            detail="No valid license found. Purchase one at /api/billing/checkout and set LICENSE_KEY in .env.",
        )

    content = await file.read()
    try:
        raw_leads = parse_leads_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not raw_leads:
        raise HTTPException(status_code=400, detail="No leads found in file.")

    scored: list[ScoredLead] = []
    for lead in raw_leads:
        enriched = enrich_lead(lead)
        scored_lead = score_lead(enriched)
        scored.append(scored_lead)
        maybe_alert(tenant.id, scored_lead)

    storage.upsert_leads(tenant.id, scored)
    return storage.list_leads(tenant.id)


@router.get("", response_model=list[ScoredLead])
def get_leads(tenant: storage.Tenant = Depends(get_current_tenant)):
    return storage.list_leads(tenant.id)


@router.get("/{lead_id}", response_model=ScoredLead)
def get_lead(lead_id: str, tenant: storage.Tenant = Depends(get_current_tenant)):
    lead = storage.get_lead(tenant.id, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
