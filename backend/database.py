from datetime import datetime, timedelta

import aiosqlite
import structlog

from config import settings

log = structlog.get_logger()
DB_PATH = settings.DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS poll_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    router_up   INTEGER NOT NULL DEFAULT 1,
    wan_ip      TEXT,
    uptime_secs INTEGER
);

CREATE TABLE IF NOT EXISTS downstream_channels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     INTEGER NOT NULL REFERENCES poll_snapshots(id) ON DELETE CASCADE,
    channel_id      INTEGER,
    frequency_hz    INTEGER,
    power_dbmv      REAL,
    snr_db          REAL,
    modulation      TEXT,
    lock_status     TEXT,
    corrected       INTEGER DEFAULT 0,
    uncorrectables  INTEGER DEFAULT 0,
    docsis_version  TEXT DEFAULT '3.0'
);

CREATE TABLE IF NOT EXISTS upstream_channels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     INTEGER NOT NULL REFERENCES poll_snapshots(id) ON DELETE CASCADE,
    channel_id      INTEGER,
    frequency_hz    INTEGER,
    power_dbmv      REAL,
    channel_type    TEXT,
    t1_timeouts     INTEGER DEFAULT 0,
    t2_timeouts     INTEGER DEFAULT 0,
    t3_timeouts     INTEGER DEFAULT 0,
    t4_timeouts     INTEGER DEFAULT 0,
    docsis_version  TEXT DEFAULT '3.0'
);

CREATE TABLE IF NOT EXISTS event_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES poll_snapshots(id) ON DELETE SET NULL,
    ts          TEXT NOT NULL,
    priority    INTEGER,
    severity    TEXT,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fired_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    resolved_at TEXT,
    severity    TEXT NOT NULL,
    alert_key   TEXT NOT NULL,
    channel_id  INTEGER,
    metric      TEXT,
    value       REAL,
    threshold   REAL,
    message     TEXT,
    notified    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON poll_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_ds_snapshot  ON downstream_channels(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_us_snapshot  ON upstream_channels(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_alerts_key   ON alerts(alert_key, resolved_at);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    log.info("database.init", path=DB_PATH)


async def purge_old_data():
    cutoff = (
        datetime.utcnow() - timedelta(days=settings.DATA_RETENTION_DAYS)
    ).isoformat() + "Z"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM poll_snapshots WHERE ts < ?", (cutoff,))
        await db.commit()
    log.info("database.purge", cutoff=cutoff)
