"""SQLite-backed store, so leads/alerts survive a restart.

Still single-tenant/single-file (fine for one self-hosted buyer, not for
multi-user -- multi-tenancy is deliberately deferred, see
licensing/README.md's go-to-market sequencing for why).
Leads/alerts are stored as serialized JSON rows rather than a normalized
schema: the shape is defined by the pydantic models in models.py and
changes with them, and a JSON blob means storage.py never needs a migration
just because a field was added there.
"""

import sqlite3
from pathlib import Path
from threading import Lock

from .config import DATABASE_PATH
from .models import Alert, ScoredLead

_lock = Lock()


def _connect() -> sqlite3.Connection:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS leads ("
        "id TEXT PRIMARY KEY, domain TEXT NOT NULL, combined_score REAL NOT NULL, data TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS alerts ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL, data TEXT NOT NULL)"
    )
    return conn


_conn = _connect()


def upsert_leads(leads: list[ScoredLead]) -> None:
    """Replaces any existing lead with the same domain rather than appending
    a duplicate. Each CSV parse mints a fresh Lead.id (see ingestion.py), so
    without this, re-uploading the same or an updated export would duplicate
    every row instead of refreshing it.
    """
    with _lock, _conn:
        domains = [lead.domain for lead in leads]
        _conn.executemany("DELETE FROM leads WHERE domain = ?", [(d,) for d in domains])
        _conn.executemany(
            "INSERT OR REPLACE INTO leads (id, domain, combined_score, data) VALUES (?, ?, ?, ?)",
            [(lead.id, lead.domain, lead.combined_score, lead.model_dump_json()) for lead in leads],
        )


def get_lead(lead_id: str) -> ScoredLead | None:
    with _lock:
        row = _conn.execute("SELECT data FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return ScoredLead.model_validate_json(row[0]) if row else None


def update_lead(lead: ScoredLead) -> None:
    with _lock, _conn:
        _conn.execute(
            "INSERT OR REPLACE INTO leads (id, domain, combined_score, data) VALUES (?, ?, ?, ?)",
            (lead.id, lead.domain, lead.combined_score, lead.model_dump_json()),
        )


def list_leads() -> list[ScoredLead]:
    with _lock:
        rows = _conn.execute("SELECT data FROM leads ORDER BY combined_score DESC").fetchall()
    return [ScoredLead.model_validate_json(row[0]) for row in rows]


def add_alert(alert: Alert) -> None:
    with _lock, _conn:
        _conn.execute("INSERT INTO alerts (id, data) VALUES (?, ?)", (alert.id, alert.model_dump_json()))


def list_alerts() -> list[Alert]:
    with _lock:
        rows = _conn.execute("SELECT data FROM alerts ORDER BY seq DESC").fetchall()
    return [Alert.model_validate_json(row[0]) for row in rows]


def clear_all() -> None:
    with _lock, _conn:
        _conn.execute("DELETE FROM leads")
        _conn.execute("DELETE FROM alerts")


def _reset_for_tests(path: str) -> None:
    """Test-only: repoints storage at a fresh DB file (e.g. ':memory:' or a
    tmp_path fixture) so tests don't share state with a real dev database.
    """
    global _conn, DATABASE_PATH
    DATABASE_PATH = path
    _conn.close()
    _conn = _connect()
