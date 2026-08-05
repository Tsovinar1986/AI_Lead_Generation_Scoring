"""Salesforce push.

Writes combined_score, bucket, LLM rationale, and outreach draft back onto
the CRM record. Falls back to a simulated (logged, no-op) push when the
relevant credentials aren't configured, or if a live call fails — so the
pipeline never breaks on a CRM outage.

The matching custom Lead fields (`Fit_Score__c` etc.) are best-effort
auto-created via the Tooling API on first push (see _ensure_salesforce_fields
below) -- this is metadata deployment, which is slower/finickier and depends
on the API user's "Customize Application" permission, so treat it as
"usually works," not guaranteed; a failure here logs a warning and the push
still falls back to mock rather than blocking.
"""

from loguru import logger

from ..config import SALESFORCE_PASSWORD, SALESFORCE_SECURITY_TOKEN, SALESFORCE_USERNAME
from ..models import CrmPushResponse, ScoredLead


def _mock_push(lead: ScoredLead, crm: str, reason: str) -> CrmPushResponse:
    logger.info(
        "CRM push (stub): {} -> {} score={} bucket={}",
        lead.company_name,
        crm,
        lead.combined_score,
        lead.bucket,
    )
    return CrmPushResponse(
        lead_id=lead.id,
        crm=crm,
        status="simulated",
        detail=(
            f"{reason} — this is a mock push. Would have written "
            f"combined_score={lead.combined_score}, bucket={lead.bucket}, "
            f"rationale, and outreach draft as custom fields/tasks on the "
            f"{crm} record for {lead.company_name}."
        ),
    )


_SALESFORCE_LEAD_FIELDS = [
    {"name": "Fit_Score__c", "label": "Fit Score", "type": "Number", "precision": 5, "scale": 1},
    {"name": "Combined_Score__c", "label": "Combined Score", "type": "Number", "precision": 5, "scale": 1},
    {"name": "Lead_Bucket__c", "label": "Lead Bucket", "type": "Text", "length": 20},
    {"name": "LLM_Rationale__c", "label": "LLM Rationale", "type": "LongTextArea", "length": 4096, "visibleLines": 6},
    {"name": "Outreach_Draft__c", "label": "Outreach Draft", "type": "LongTextArea", "length": 4096, "visibleLines": 6},
]

_salesforce_fields_ready = False


def _ensure_salesforce_fields(sf) -> None:
    """Best-effort auto-create the custom Lead fields this app writes to via
    the Tooling API. Field creation needs "Customize Application" on the API
    user and is eventually-consistent (a field created here may not be
    immediately writable) -- so failures here are logged and swallowed, never
    raised, and the caller's own try/except around _salesforce_push already
    falls back to a mock push if a field genuinely isn't ready yet.
    """
    global _salesforce_fields_ready
    if _salesforce_fields_ready:
        return

    try:
        existing = sf.toolingexecute(
            "query/?q=SELECT+DeveloperName+FROM+CustomField+WHERE+TableEnumOrId='Lead'"
        )
        existing_names = {f"{r['DeveloperName']}__c" for r in existing.get("records", [])}

        for field in _SALESFORCE_LEAD_FIELDS:
            if field["name"] in existing_names:
                continue

            metadata = {"label": field["label"], "type": field["type"]}
            if field["type"] == "Number":
                metadata["precision"] = field["precision"]
                metadata["scale"] = field["scale"]
            elif field["type"] in ("Text", "LongTextArea"):
                metadata["length"] = field["length"]
                if field["type"] == "LongTextArea":
                    metadata["visibleLines"] = field["visibleLines"]

            sf.toolingexecute(
                "sobjects/CustomField/",
                method="POST",
                data={"FullName": f"Lead.{field['name']}", "Metadata": metadata},
            )
            logger.info("Created missing Salesforce Lead field '{}'", field["name"])
    except Exception as exc:  # noqa: BLE001 - best-effort; a real push failure surfaces separately
        logger.warning(
            "Couldn't auto-create/verify Salesforce custom fields (needs 'Customize "
            "Application' permission on the API user) — push may fail until they exist: {}",
            exc,
        )

    _salesforce_fields_ready = True


def _salesforce_push(lead: ScoredLead) -> CrmPushResponse:
    from simple_salesforce import Salesforce

    sf = Salesforce(
        username=SALESFORCE_USERNAME,
        password=SALESFORCE_PASSWORD,
        security_token=SALESFORCE_SECURITY_TOKEN,
    )
    _ensure_salesforce_fields(sf)

    safe_domain = lead.domain.replace("'", "\\'")
    existing = sf.query(f"SELECT Id FROM Lead WHERE Website = '{safe_domain}' LIMIT 1")

    fields = {
        "Company": lead.company_name,
        "Website": lead.domain,
        "Fit_Score__c": lead.fit_score,
        "Combined_Score__c": lead.combined_score,
        "Lead_Bucket__c": lead.bucket,
        "LLM_Rationale__c": lead.llm_rationale,
        "Outreach_Draft__c": lead.outreach_draft or "",
    }

    if existing["totalSize"] > 0:
        record_id = existing["records"][0]["Id"]
        sf.Lead.update(record_id, fields)
        detail = f"Updated existing Salesforce Lead {record_id} for {lead.company_name}."
    else:
        fields["LastName"] = lead.contact_name or "Unknown"
        created = sf.Lead.create(fields)
        record_id = created["id"]
        detail = f"Created new Salesforce Lead {record_id} for {lead.company_name}."

    return CrmPushResponse(lead_id=lead.id, crm="salesforce", status="success", detail=detail)


def push_to_crm(lead: ScoredLead, crm: str = "salesforce") -> CrmPushResponse:
    if crm == "salesforce":
        if not (SALESFORCE_USERNAME and SALESFORCE_PASSWORD and SALESFORCE_SECURITY_TOKEN):
            return _mock_push(lead, crm, "No SALESFORCE_* credentials configured")
        try:
            return _salesforce_push(lead)
        except Exception as exc:  # noqa: BLE001 - fall back rather than break the pipeline
            logger.warning("Salesforce push failed for {}: {}", lead.company_name, exc)
            return _mock_push(lead, crm, f"Live Salesforce push failed ({exc})")

    return _mock_push(lead, crm, f"Unknown CRM '{crm}'")
