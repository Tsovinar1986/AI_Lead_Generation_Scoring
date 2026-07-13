"""In-memory store for the demo. Swap for a real DB when moving past v1."""

from threading import Lock

from .models import Alert, ScoredLead

_lock = Lock()
_leads: dict[str, ScoredLead] = {}
_alerts: list[Alert] = []


def upsert_leads(leads: list[ScoredLead]) -> None:
    """Replaces any existing lead with the same domain rather than appending
    a duplicate. Each CSV parse mints a fresh Lead.id (see ingestion.py), so
    without this, re-uploading the same or an updated export would duplicate
    every row instead of refreshing it.
    """
    with _lock:
        incoming_domains = {lead.domain for lead in leads}
        for existing_id, existing_lead in list(_leads.items()):
            if existing_lead.domain in incoming_domains:
                del _leads[existing_id]
        for lead in leads:
            _leads[lead.id] = lead


def get_lead(lead_id: str) -> ScoredLead | None:
    with _lock:
        return _leads.get(lead_id)


def update_lead(lead: ScoredLead) -> None:
    with _lock:
        _leads[lead.id] = lead


def list_leads() -> list[ScoredLead]:
    with _lock:
        return sorted(_leads.values(), key=lambda l: l.combined_score, reverse=True)


def add_alert(alert: Alert) -> None:
    with _lock:
        _alerts.append(alert)


def list_alerts() -> list[Alert]:
    with _lock:
        return list(reversed(_alerts))


def clear_all() -> None:
    with _lock:
        _leads.clear()
        _alerts.clear()
