import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import settings
from database import init_db, DB_PATH, purge_old_data
from scraper import poll_router
from alerting import evaluate_snapshot
from diagnostics import get_diagnostics, get_history
from metrics import update_metrics, get_metrics_output

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
log = structlog.get_logger()

_latest_snapshot = None
_scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    _scheduler.add_job(run_poll_cycle, "interval", seconds=settings.POLL_INTERVAL,
                       id="poll", replace_existing=True)
    _scheduler.add_job(purge_old_data, "interval", hours=24,
                       id="purge", replace_existing=True)
    _scheduler.start()
    log.info("app.started", poll_interval=settings.POLL_INTERVAL,
             router=settings.router_base_url)
    asyncio.create_task(run_poll_cycle())
    yield
    _scheduler.shutdown()


app = FastAPI(title="DOCSIS Monitor", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

security = HTTPBasic(auto_error=False)


def optional_auth(creds: Optional[HTTPBasicCredentials] = Depends(security)):
    if not settings.BASIC_AUTH_USER:
        return True
    if not creds:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    ok = (
        secrets.compare_digest(creds.username, settings.BASIC_AUTH_USER) and
        secrets.compare_digest(creds.password, settings.BASIC_AUTH_PASS or "")
    )
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    return True


def _row_dict(row) -> dict:
    return dict(zip(row.keys(), row))


async def run_poll_cycle():
    global _latest_snapshot
    try:
        snap = await poll_router()
        _latest_snapshot = snap
        update_metrics(snap)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "INSERT INTO poll_snapshots (router_up,wan_ip,uptime_secs) VALUES (?,?,?)",
                (1 if snap.router_up else 0, snap.wan_ip, snap.uptime_secs),
            ) as cur:
                snap_id = cur.lastrowid
            for ch in snap.downstream:
                await db.execute(
                    """INSERT INTO downstream_channels
                       (snapshot_id,channel_id,frequency_hz,power_dbmv,snr_db,modulation,
                        lock_status,corrected,uncorrectables,docsis_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (snap_id, ch.channel_id, ch.frequency_hz, ch.power_dbmv, ch.snr_db,
                     ch.modulation, ch.lock_status, ch.corrected, ch.uncorrectables,
                     ch.docsis_version),
                )
            for ch in snap.upstream:
                await db.execute(
                    """INSERT INTO upstream_channels
                       (snapshot_id,channel_id,frequency_hz,power_dbmv,channel_type,
                        t1_timeouts,t2_timeouts,t3_timeouts,t4_timeouts,docsis_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (snap_id, ch.channel_id, ch.frequency_hz, ch.power_dbmv,
                     ch.channel_type, ch.t1_timeouts, ch.t2_timeouts,
                     ch.t3_timeouts, ch.t4_timeouts, ch.docsis_version),
                )
            for ev in snap.event_logs[-200:]:
                await db.execute(
                    "INSERT INTO event_logs (snapshot_id,ts,priority,severity,message)"
                    " VALUES (?,?,?,?,?)",
                    (snap_id, ev.ts, ev.priority, ev.severity, ev.message),
                )
            await db.commit()
            await evaluate_snapshot(db, snap)
    except Exception as e:
        log.error("poll_cycle.failed", error=str(e), exc_info=settings.DEBUG)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "router_ip": settings.ROUTER_IP,
        "last_poll": _latest_snapshot.polled_at.isoformat() if _latest_snapshot else None,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    data, ct = get_metrics_output()
    return Response(content=data, media_type=ct)


@app.get("/api/v1/overview", dependencies=[Depends(optional_auth)])
async def overview():
    if not _latest_snapshot:
        raise HTTPException(503, "Poll pending")
    snap = _latest_snapshot
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL AND severity='critical'"
        ) as cur:
            open_crit = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL AND severity='warn'"
        ) as cur:
            open_warn = (await cur.fetchone())[0]
    status = "CRITICAL" if open_crit else ("WARNING" if open_warn else "OK")
    return {
        "router_up": snap.router_up,
        "status": status,
        "open_critical": open_crit,
        "open_warn": open_warn,
        "wan_ip": snap.wan_ip,
        "uptime_secs": snap.uptime_secs,
        "downstream_count": len(snap.downstream),
        "upstream_count": len(snap.upstream),
        "last_poll": snap.polled_at.isoformat() + "Z",
        "poll_interval_secs": settings.POLL_INTERVAL,
    }


@app.get("/api/v1/downstream", dependencies=[Depends(optional_auth)])
async def downstream():
    if not _latest_snapshot:
        raise HTTPException(503, "Poll pending")
    return {
        "polled_at": _latest_snapshot.polled_at.isoformat() + "Z",
        "channels": [
            {**ch.model_dump(),
             "power_status": ch.power_status.value,
             "snr_status": ch.snr_status.value,
             "uncorrectable_status": ch.uncorrectable_status.value}
            for ch in _latest_snapshot.downstream
        ],
    }


@app.get("/api/v1/upstream", dependencies=[Depends(optional_auth)])
async def upstream_api():
    if not _latest_snapshot:
        raise HTTPException(503, "Poll pending")
    return {
        "polled_at": _latest_snapshot.polled_at.isoformat() + "Z",
        "channels": [
            {**ch.model_dump(),
             "power_status": ch.power_status.value,
             "timeout_severity": ch.timeout_severity.value}
            for ch in _latest_snapshot.upstream
        ],
    }


@app.get("/api/v1/logs", dependencies=[Depends(optional_auth)])
async def event_logs(
    severity: Optional[str] = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where, params = "WHERE 1=1", []
        if severity:
            where += " AND severity=?"
            params.append(severity.upper())
        async with db.execute(
            f"SELECT * FROM event_logs {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ) as cur:
            rows = await cur.fetchall()
    return {"logs": [_row_dict(r) for r in rows]}


@app.get("/api/v1/diagnostics", dependencies=[Depends(optional_auth)])
async def diagnostics():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await get_diagnostics(db)


@app.get("/api/v1/alerts", dependencies=[Depends(optional_auth)])
async def alerts_api(open_only: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE resolved_at IS NULL" if open_only else ""
        async with db.execute(
            f"SELECT * FROM alerts {where} ORDER BY fired_at DESC LIMIT 500"
        ) as cur:
            rows = await cur.fetchall()
    return {"alerts": [_row_dict(r) for r in rows]}


@app.get("/api/v1/history/{metric}", dependencies=[Depends(optional_auth)])
async def history(metric: str, hours: int = Query(24, le=168)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        data = await get_history(db, metric, hours)
    return {"metric": metric, "hours": hours, "data": data}


@app.get("/api/v1/thresholds", dependencies=[Depends(optional_auth)])
async def thresholds():
    return {
        "downstream": {
            "power_min_dbmv": settings.DS_POWER_MIN,
            "power_max_dbmv": settings.DS_POWER_MAX,
            "snr_warn_db": settings.SNR_WARN_DB,
            "snr_crit_db": settings.SNR_CRIT_DB,
            "uncorrectable_warn": settings.UNCORRECTABLE_WARN,
            "uncorrectable_crit": settings.UNCORRECTABLE_CRIT,
        },
        "upstream": {
            "power_min_dbmv": settings.US_POWER_MIN,
            "power_max_dbmv": settings.US_POWER_MAX,
            "t3t4_crit_count": settings.T3_T4_CRIT_COUNT,
        },
        "alert_debounce_secs": settings.ALERT_DEBOUNCE_SECONDS,
    }
