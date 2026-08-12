from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile

from .. import storage
from ..auth import get_current_tenant
from ..config import LICENSE_REQUIRED, RATE_LIMIT_UPLOAD, TRIAL_MAX_LEADS_PER_UPLOAD
from ..licensing import trial_days_left, trial_uploads_left, verify_license
from ..middleware import limiter
from ..models import ScoredLead
from ..services.alerts import maybe_alert
from ..services.enrichment import enrich_lead
from ..services.ingestion import parse_leads_file
from ..services.scoring import score_lead
from ..services.upload_validation import enforce_row_cap, validate_upload_file

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("/upload", response_model=list[ScoredLead])
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_leads(
    request: Request,
    response: Response,
    file: UploadFile,
    tenant: storage.Tenant = Depends(get_current_tenant),
):
    # Only the default tenant (no Authorization header -- the self-hosted
    # buyer using this instance directly) is ever gated by this deployment's
    # own license. A self-serve tenant (routers/accounts.py) is a customer
    # of whoever runs this deployment, not a buyer of the software itself,
    # so their uploads are never blocked or capped here.
    gated = tenant.id == storage.DEFAULT_TENANT_ID and verify_license() is None
    if gated and (LICENSE_REQUIRED or trial_days_left() <= 0 or trial_uploads_left() <= 0):
        raise HTTPException(
            status_code=402,
            detail="No valid license found and the free trial has ended. "
            "Purchase one at /api/billing/checkout and set LICENSE_KEY in .env, "
            "or sign up for your own workspace at /api/accounts/signup.",
        )

    content = await file.read()
    validate_upload_file(file.filename, content)
    try:
        raw_leads = parse_leads_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not raw_leads:
        raise HTTPException(status_code=400, detail="No leads found in file.")
    enforce_row_cap(len(raw_leads))

    # Trial row cap: judge scoring quality on a real sample without full
    # free use of a large list.
    if gated and len(raw_leads) > TRIAL_MAX_LEADS_PER_UPLOAD:
        response.headers["X-Trial-Limited-Rows"] = str(TRIAL_MAX_LEADS_PER_UPLOAD)
        response.headers["X-Trial-Total-Rows"] = str(len(raw_leads))
        raw_leads = raw_leads[:TRIAL_MAX_LEADS_PER_UPLOAD]

    if gated:
        storage.increment_trial_uploads()

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
