"""SQLite storage.

Deliberately a single file on a persistent volume: the working set is a few
days of headlines (tens of MB), reads massively outnumber writes, and one
process owns it. WAL keeps API reads from blocking behind the refresh job.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

DB_PATH = Path(os.environ.get("NEWSFIN_DB", "./data/newsfin.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cluster (
    id              INTEGER PRIMARY KEY,
    lead_title      TEXT    NOT NULL,
    lead_url        TEXT    NOT NULL,
    lead_source     TEXT    NOT NULL,
    summary         TEXT    NOT NULL DEFAULT '',
    tokens          TEXT    NOT NULL,
    entities        TEXT    NOT NULL DEFAULT '',
    region          TEXT    NOT NULL,
    regions         TEXT    NOT NULL DEFAULT '',
    topics          TEXT    NOT NULL DEFAULT '',
    locales         TEXT    NOT NULL DEFAULT '',
    first_seen      TEXT    NOT NULL,
    published       TEXT    NOT NULL,
    last_update     TEXT    NOT NULL,
    n_sources       INTEGER NOT NULL DEFAULT 1,
    n_aggregators   INTEGER NOT NULL DEFAULT 0,
    n_angles        INTEGER NOT NULL DEFAULT 1,
    max_authority   REAL    NOT NULL DEFAULT 0,
    mean_authority  REAL    NOT NULL DEFAULT 0,
    best_position   INTEGER NOT NULL DEFAULT 99,
    impact          REAL    NOT NULL DEFAULT 0,
    breakdown       TEXT    NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cluster_impact   ON cluster(impact DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_pub      ON cluster(published DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_region   ON cluster(region, impact DESC);

CREATE TABLE IF NOT EXISTS article (
    id          INTEGER PRIMARY KEY,
    cluster_id  INTEGER NOT NULL REFERENCES cluster(id) ON DELETE CASCADE,
    source_key  TEXT    NOT NULL,
    source_name TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    url_key     TEXT    NOT NULL UNIQUE,
    published   TEXT    NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    authority   REAL    NOT NULL DEFAULT 0.5,
    aggregator  INTEGER NOT NULL DEFAULT 0,
    subgroup    INTEGER NOT NULL DEFAULT 0,
    region      TEXT    NOT NULL DEFAULT '',
    topics      TEXT    NOT NULL DEFAULT '',
    locale      TEXT
);

CREATE INDEX IF NOT EXISTS idx_article_cluster ON article(cluster_id);
CREATE INDEX IF NOT EXISTS idx_article_pub     ON article(published DESC);

CREATE TABLE IF NOT EXISTS feed_health (
    source_key   TEXT PRIMARY KEY,
    last_ok      TEXT,
    last_error   TEXT,
    last_status  INTEGER,
    ok_count     INTEGER NOT NULL DEFAULT 0,
    fail_count   INTEGER NOT NULL DEFAULT 0,
    last_entries INTEGER NOT NULL DEFAULT 0,
    etag         TEXT,
    modified     TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Standalone (not external-content) FTS index: it owns its own copy of the
-- text. External-content tables cannot be updated with plain DELETE/INSERT,
-- and the cluster rows are rewritten on every rescore.
CREATE VIRTUAL TABLE IF NOT EXISTS cluster_fts USING fts5(
    lead_title, summary, tokenize='porter'
);
"""

_local = threading.local()


def connect() -> sqlite3.Connection:
    if getattr(_local, "conn", None) is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        _local.conn = conn
    return _local.conn


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def set_meta(key: str, value) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )


def get_meta(key: str, default=None):
    row = connect().execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def prune(max_age_days: int = 5) -> int:
    """Drop anything past the retention window. Keeps the DB small and the
    corroboration counts honest - a 3-week-old story shouldn't accumulate."""
    cutoff = (datetime.now(UTC) - timedelta(days=max_age_days)).isoformat()
    with tx() as c:
        c.execute("DELETE FROM article WHERE published < ?", (cutoff,))
        cur = c.execute(
            "DELETE FROM cluster WHERE id NOT IN (SELECT DISTINCT cluster_id FROM article)"
        )
        n = cur.rowcount
        c.execute("DELETE FROM cluster_fts")
        c.execute(
            "INSERT INTO cluster_fts(rowid, lead_title, summary) "
            "SELECT id, lead_title, summary FROM cluster"
        )
    return n
