"""HubSpot/Salesforce push.

Writes combined_score, bucket, LLM rationale, and outreach draft back onto
the CRM record. Falls back to a simulated (logged, no-op) push when the
relevant credentials aren't configured, or if a live call fails — so the
pipeline never breaks on a CRM outage.

HubSpot: the five custom company properties this needs (`fit_score`,
`combined_score`, `lead_bucket`, `llm_rationale`, `outreach_draft`) are
created automatically on first push via the Properties API if missing --
no manual portal setup required, just an access token with the
`crm.schemas.companies.write` scope.
Salesforce: the matching custom Lead fields (`Fit_Score__c` etc.) are
best-effort auto-created via the Tooling API on first push (see
_ensure_salesforce_fields below) -- unlike HubSpot's Properties API this is
metadata deployment, which is slower/finickier and depends on the API
user's "Customize Application" permission, so treat it as "usually works,"
not guaranteed; a failure here logs a warning and the push still falls back
to mock rather than blocking.
"""

from loguru import logger

from ..config import (
    HUBSPOT_ACCESS_TOKEN,
    SALESFORCE_PASSWORD,
    SALESFORCE_SECURITY_TOKEN,
    SALESFORCE_USERNAME,
)
from ..models import CrmPushResponse, ScoredLead

_HUBSPOT_COMPANY_PROPERTIES = [
    {"name": "fit_score", "label": "Fit Score", "type": "number", "fieldType": "number"},
    {"name": "combined_score", "label": "Combined Score", "type": "number", "fieldType": "number"},
    {"name": "lead_bucket", "label": "Lead Bucket", "type": "string", "fieldType": "text"},
    {"name": "llm_rationale", "label": "LLM Rationale", "type": "string", "fieldType": "textarea"},
    {"name": "outreach_draft", "label": "Outreach Draft", "type": "string", "fieldType": "textarea"},
]

_hubspot_properties_ready = False


def _ensure_hubspot_properties(client) -> None:
    """Idempotently create the custom company properties this app writes to.

    Runs once per process (cached in _hubspot_properties_ready) rather than
    before every push, since it's a portal-schema check, not per-lead data.
    """
    global _hubspot_properties_ready
    if _hubspot_properties_ready:
        return

    from hubspot.crm.properties import ApiException, PropertyCreate

    for prop in _HUBSPOT_COMPANY_PROPERTIES:
        try:
            client.crm.properties.core_api.get_by_name("companies", prop["name"])
        except ApiException as exc:
            if exc.status != 404:
                raise
            client.crm.properties.core_api.create(
                "companies",
                PropertyCreate(
                    name=prop["name"],
                    label=prop["label"],
                    type=prop["type"],
                    field_type=prop["fieldType"],
                    group_name="companyinformation",
                ),
            )
            logger.info("Created missing HubSpot company property '{}'", prop["name"])

    _hubspot_properties_ready = True


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


def _hubspot_push(lead: ScoredLead) -> CrmPushResponse:
    from hubspot import HubSpot
    from hubspot.crm.companies import SimplePublicObjectInput

    client = HubSpot(access_token=HUBSPOT_ACCESS_TOKEN)
    _ensure_hubspot_properties(client)
    properties = {
        "name": lead.company_name,
        "domain": lead.domain,
        "fit_score": lead.fit_score,
        "combined_score": lead.combined_score,
        "lead_bucket": lead.bucket,
        "llm_rationale": lead.llm_rationale,
        "outreach_draft": lead.outreach_draft or "",
    }

    search = client.crm.companies.search_api.do_search(
        public_object_search_request={
            "filterGroups": [
                {"filters": [{"propertyName": "domain", "operator": "EQ", "value": lead.domain}]}
            ],
            "limit": 1,
        }
    )

    if search.results:
        company_id = search.results[0].id
        client.crm.companies.basic_api.update(
            company_id, simple_public_object_input=SimplePublicObjectInput(properties=properties)
        )
        detail = f"Updated existing HubSpot company {company_id} for {lead.company_name}."
    else:
        created = client.crm.companies.basic_api.create(
            simple_public_object_input_for_create=SimplePublicObjectInput(properties=properties)
        )
        company_id = created.id
        detail = f"Created new HubSpot company {company_id} for {lead.company_name}."

    return CrmPushResponse(lead_id=lead.id, crm="hubspot", status="success", detail=detail)


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


def push_to_crm(lead: ScoredLead, crm: str = "hubspot") -> CrmPushResponse:
    if crm == "hubspot":
        if not HUBSPOT_ACCESS_TOKEN:
            return _mock_push(lead, crm, "No HUBSPOT_ACCESS_TOKEN configured")
        try:
            return _hubspot_push(lead)
        except Exception as exc:  # noqa: BLE001 - fall back rather than break the pipeline
            logger.warning("HubSpot push failed for {}: {}", lead.company_name, exc)
            return _mock_push(lead, crm, f"Live HubSpot push failed ({exc})")

    if crm == "salesforce":
        if not (SALESFORCE_USERNAME and SALESFORCE_PASSWORD and SALESFORCE_SECURITY_TOKEN):
            return _mock_push(lead, crm, "No SALESFORCE_* credentials configured")
        try:
            return _salesforce_push(lead)
        except Exception as exc:  # noqa: BLE001 - fall back rather than break the pipeline
            logger.warning("Salesforce push failed for {}: {}", lead.company_name, exc)
            return _mock_push(lead, crm, f"Live Salesforce push failed ({exc})")

    return _mock_push(lead, crm, f"Unknown CRM '{crm}'")
