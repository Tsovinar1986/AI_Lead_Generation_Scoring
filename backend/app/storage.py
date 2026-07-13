"""SQLite-backed store, so leads/alerts survive a restart.

Multi-tenant: every lead/alert row carries a tenant_id, and every read/write
here takes one. Requests with no Authorization header (see auth.py) are
scoped to DEFAULT_TENANT_ID -- a sentinel, not a real provisioned tenant --
so a single self-hosted buyer gets the exact same zero-config behavior as
before this existed. A seller running one shared instance for multiple
customers provisions real tenants (backend/scripts/create_tenant.py) with
their own API key, and their data never overlaps with anyone else's.

Leads/alerts are stored as serialized JSON rows rather than a normalized
schema: the shape is defined by the pydantic models in models.py and
changes with them, and a JSON blob means storage.py never needs a migration
just because a field was added there.
"""

import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from .config import DATABASE_PATH
from .models import Alert, ScoredLead

DEFAULT_TENANT_ID = "default"

_lock = Lock()


@dataclass
class Tenant:
    id: str
    name: str


def _connect() -> sqlite3.Connection:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS leads ("
        "id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT NOT NULL, "
        "combined_score REAL NOT NULL, data TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads (tenant_id)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS alerts ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL, tenant_id TEXT NOT NULL, data TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts (tenant_id)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenants ("
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, api_key_hash TEXT NOT NULL UNIQUE, created_at REAL NOT NULL)"
    )
    return conn


_conn = _connect()


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_tenant(name: str) -> tuple[Tenant, str]:
    """Provisions a new tenant with a fresh API key. The plaintext key is
    returned once, here, and never stored -- only its hash is. Give it to
    the customer immediately; there's no way to recover it later, only to
    provision a new one.
    """
    tenant_id = secrets.token_hex(8)
    api_key = secrets.token_urlsafe(32)
    with _lock, _conn:
        _conn.execute(
            "INSERT INTO tenants (id, name, api_key_hash, created_at) VALUES (?, ?, ?, ?)",
            (tenant_id, name, _hash_key(api_key), time.time()),
        )
    return Tenant(id=tenant_id, name=name), api_key


def get_tenant_by_api_key(api_key: str) -> Tenant | None:
    with _lock:
        row = _conn.execute(
            "SELECT id, name FROM tenants WHERE api_key_hash = ?", (_hash_key(api_key),)
        ).fetchone()
    return Tenant(id=row[0], name=row[1]) if row else None


def upsert_leads(tenant_id: str, leads: list[ScoredLead]) -> None:
    """Replaces any existing lead with the same domain (within this tenant)
    rather than appending a duplicate. Each CSV parse mints a fresh Lead.id
    (see ingestion.py), so without this, re-uploading the same or an updated
    export would duplicate every row instead of refreshing it.
    """
    with _lock, _conn:
        domains = [lead.domain for lead in leads]
        _conn.executemany(
            "DELETE FROM leads WHERE tenant_id = ? AND domain = ?", [(tenant_id, d) for d in domains]
        )
        _conn.executemany(
            "INSERT OR REPLACE INTO leads (id, tenant_id, domain, combined_score, data) VALUES (?, ?, ?, ?, ?)",
            [
                (lead.id, tenant_id, lead.domain, lead.combined_score, lead.model_dump_json())
                for lead in leads
            ],
        )


def get_lead(tenant_id: str, lead_id: str) -> ScoredLead | None:
    with _lock:
        row = _conn.execute(
            "SELECT data FROM leads WHERE tenant_id = ? AND id = ?", (tenant_id, lead_id)
        ).fetchone()
    return ScoredLead.model_validate_json(row[0]) if row else None


def update_lead(tenant_id: str, lead: ScoredLead) -> None:
    with _lock, _conn:
        _conn.execute(
            "INSERT OR REPLACE INTO leads (id, tenant_id, domain, combined_score, data) VALUES (?, ?, ?, ?, ?)",
            (lead.id, tenant_id, lead.domain, lead.combined_score, lead.model_dump_json()),
        )


def list_leads(tenant_id: str) -> list[ScoredLead]:
    with _lock:
        rows = _conn.execute(
            "SELECT data FROM leads WHERE tenant_id = ? ORDER BY combined_score DESC", (tenant_id,)
        ).fetchall()
    return [ScoredLead.model_validate_json(row[0]) for row in rows]


def add_alert(tenant_id: str, alert: Alert) -> None:
    with _lock, _conn:
        _conn.execute(
            "INSERT INTO alerts (id, tenant_id, data) VALUES (?, ?, ?)",
            (alert.id, tenant_id, alert.model_dump_json()),
        )


def list_alerts(tenant_id: str) -> list[Alert]:
    with _lock:
        rows = _conn.execute(
            "SELECT data FROM alerts WHERE tenant_id = ? ORDER BY seq DESC", (tenant_id,)
        ).fetchall()
    return [Alert.model_validate_json(row[0]) for row in rows]


def clear_all(tenant_id: str) -> None:
    with _lock, _conn:
        _conn.execute("DELETE FROM leads WHERE tenant_id = ?", (tenant_id,))
        _conn.execute("DELETE FROM alerts WHERE tenant_id = ?", (tenant_id,))


def _reset_for_tests(path: str) -> None:
    """Test-only: repoints storage at a fresh DB file (e.g. ':memory:' or a
    tmp_path fixture) so tests don't share state with a real dev database.
    """
    global _conn, DATABASE_PATH
    DATABASE_PATH = path
    _conn.close()
    _conn = _connect()
