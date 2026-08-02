from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import storage
from ..auth import get_current_tenant
from ..config import RATE_LIMIT_UPLOAD
from ..middleware import limiter
from ..models import Alert, CrmPushResponse, OutreachRequest, OutreachResponse
from ..services.crm import push_to_crm
from ..services.outreach import generate_outreach_draft

router = APIRouter(prefix="/api/leads", tags=["actions"])
alerts_router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _get_or_404(tenant_id: str, lead_id: str):
    lead = storage.get_lead(tenant_id, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# Same tier as the upload endpoints -- each call here hits a real,
# potentially-billed third-party API (Anthropic/HubSpot/Salesforce) per lead.
@router.post("/{lead_id}/outreach", response_model=OutreachResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
def create_outreach_draft(
    request: Request,
    lead_id: str,
    body: OutreachRequest,
    tenant: storage.Tenant = Depends(get_current_tenant),
):
    lead = _get_or_404(tenant.id, lead_id)
    draft = generate_outreach_draft(lead, channel=body.channel)
    lead.outreach_draft = draft
    storage.update_lead(tenant.id, lead)
    return OutreachResponse(lead_id=lead_id, channel=body.channel, draft=draft)


@router.post("/{lead_id}/crm-push", response_model=CrmPushResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
def crm_push(
    request: Request,
    lead_id: str,
    crm: Literal["hubspot", "salesforce"] = "hubspot",
    tenant: storage.Tenant = Depends(get_current_tenant),
):
    lead = _get_or_404(tenant.id, lead_id)
    result = push_to_crm(lead, crm=crm)
    lead.crm_pushed = True
    storage.update_lead(tenant.id, lead)
    return result


@alerts_router.get("", response_model=list[Alert])
def get_alerts(tenant: storage.Tenant = Depends(get_current_tenant)):
    return storage.list_alerts(tenant.id)
