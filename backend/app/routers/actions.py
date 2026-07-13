from fastapi import APIRouter, HTTPException

from .. import storage
from ..models import Alert, CrmPushResponse, OutreachRequest, OutreachResponse
from ..services.crm import push_to_crm
from ..services.outreach import generate_outreach_draft

router = APIRouter(prefix="/api/leads", tags=["actions"])
alerts_router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _get_or_404(lead_id: str):
    lead = storage.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/{lead_id}/outreach", response_model=OutreachResponse)
def create_outreach_draft(lead_id: str, body: OutreachRequest):
    lead = _get_or_404(lead_id)
    draft = generate_outreach_draft(lead, channel=body.channel)
    lead.outreach_draft = draft
    storage.update_lead(lead)
    return OutreachResponse(lead_id=lead_id, channel=body.channel, draft=draft)


@router.post("/{lead_id}/crm-push", response_model=CrmPushResponse)
def crm_push(lead_id: str, crm: str = "hubspot"):
    lead = _get_or_404(lead_id)
    result = push_to_crm(lead, crm=crm)
    lead.crm_pushed = True
    storage.update_lead(lead)
    return result


@alerts_router.get("", response_model=list[Alert])
def get_alerts():
    return storage.list_alerts()
