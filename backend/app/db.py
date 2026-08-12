"""Tiny DB-agnostic connection layer so storage.py can run on SQLite
(zero-config default, no setup needed -- the original behavior of this app)
or PostgreSQL (set DATABASE_URL) without pulling in a full ORM. storage.py
writes plain SQL with '?' placeholders throughout, same as it always has for
SQLite; this module is the only place that knows psycopg2 uses '%s'
instead, or that upsert/autoincrement/schema-introspection syntax differs
between the two backends.

psycopg2 is only imported when DATABASE_URL is actually set to a
postgres(ql):// URL -- installing it is optional (see requirements.txt),
and a SQLite-only deployment (the default) never needs it.
"""

from .config import DATABASE_URL

IS_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")


class _PGConnection:
    """Wraps a psycopg2 connection so it exposes the same connection-level
    .execute()/.executemany() convenience methods and 'with conn: ...'
    commit/rollback-on-exit semantics that sqlite3.Connection provides
    natively -- psycopg2 only exposes execute on a cursor, but storage.py
    is written once, against the sqlite3 shape, for both backends.
    """

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._raw.cursor()
        cur.executemany(sql.replace("?", "%s"), list(seq_of_params))
        return cur

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        return False

    def close(self):
        self._raw.close()


def connect():
    """A DB-API-ish connection: a real sqlite3.Connection by default, or a
    _PGConnection wrapping psycopg2 if DATABASE_URL points at Postgres.
    Either way, callers get .execute()/.executemany() with '?' placeholders
    and 'with conn: ...' transaction semantics.
    """
    if IS_POSTGRES:
        import psycopg2

        return _PGConnection(psycopg2.connect(DATABASE_URL))

    import sqlite3
    from pathlib import Path

    from .config import DATABASE_PATH

    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH, check_same_thread=False)
