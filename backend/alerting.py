"""
Alert engine: evaluates thresholds, debounces, fires webhooks/email.
"""
import asyncio
import json
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

import aiosqlite
import httpx
import structlog

from config import settings
from models import RouterSnapshot

log = structlog.get_logger()

# In-memory debounce map: alert_key -> last_fired
_debounce: dict[str, datetime] = {}


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def _open_alert(
    db: aiosqlite.Connection,
    alert_key: str,
    severity: str,
    channel_id: Optional[int],
    metric: Optional[str],
    value: Optional[float],
    threshold: Optional[float],
    message: str,
) -> Optional[int]:
    now = datetime.utcnow()
    last = _debounce.get(alert_key)
    if last and (now - last).total_seconds() < settings.ALERT_DEBOUNCE_SECONDS:
        return None

    async with db.execute(
        "SELECT id FROM alerts WHERE alert_key=? AND resolved_at IS NULL", (alert_key,)
    ) as cur:
        if await cur.fetchone():
            return None

    _debounce[alert_key] = now
    async with db.execute(
        """INSERT INTO alerts
           (severity, alert_key, channel_id, metric, value, threshold, message, notified)
           VALUES (?,?,?,?,?,?,?,0)""",
        (severity, alert_key, channel_id, metric, value, threshold, message),
    ) as cur:
        alert_id = cur.lastrowid
    await db.commit()
    log.warning("alert.opened", key=alert_key, severity=severity, msg=message)
    return alert_id


async def _resolve_alert(db: aiosqlite.Connection, alert_key: str):
    await db.execute(
        "UPDATE alerts SET resolved_at=? WHERE alert_key=? AND resolved_at IS NULL",
        (_now_iso(), alert_key),
    )
    await db.commit()
    _debounce.pop(alert_key, None)


async def evaluate_snapshot(db: aiosqlite.Connection, snap: RouterSnapshot) -> list[dict]:
    fired: list[dict] = []

    if not snap.router_up:
        aid = await _open_alert(db, "router_down", "critical", None,
                                 "reachability", None, None,
                                 "Router is unreachable — polling failed.")
        if aid:
            fired.append({"id": aid, "severity": "critical",
                           "message": "Router unreachable."})
        return fired
    else:
        await _resolve_alert(db, "router_down")

    # Downstream
    for ch in snap.downstream:
        cid = ch.channel_id or 0

        if ch.snr_db is not None:
            if ch.snr_db < settings.SNR_CRIT_DB:
                aid = await _open_alert(
                    db, f"ds_snr_crit_{cid}", "critical", cid, "snr_db",
                    ch.snr_db, settings.SNR_CRIT_DB,
                    f"DS ch{cid}: SNR {ch.snr_db:.1f} dB < critical {settings.SNR_CRIT_DB} dB",
                )
                if aid:
                    fired.append({"id": aid, "severity": "critical",
                        "message": f"DS ch{cid} SNR {ch.snr_db:.1f} dB"})
            elif ch.snr_db < settings.SNR_WARN_DB:
                aid = await _open_alert(
                    db, f"ds_snr_warn_{cid}", "warn", cid, "snr_db",
                    ch.snr_db, settings.SNR_WARN_DB,
                    f"DS ch{cid}: SNR {ch.snr_db:.1f} dB < warn {settings.SNR_WARN_DB} dB",
                )
                if aid:
                    fired.append({"id": aid, "severity": "warn",
                        "message": f"DS ch{cid} SNR {ch.snr_db:.1f} dB"})
            else:
                await _resolve_alert(db, f"ds_snr_crit_{cid}")
                await _resolve_alert(db, f"ds_snr_warn_{cid}")

        if ch.power_dbmv is not None:
            if not (settings.DS_POWER_MIN <= ch.power_dbmv <= settings.DS_POWER_MAX):
                aid = await _open_alert(
                    db, f"ds_power_{cid}", "warn", cid, "power_dbmv",
                    ch.power_dbmv, None,
                    f"DS ch{cid}: power {ch.power_dbmv:.1f} dBmV outside "
                    f"[{settings.DS_POWER_MIN}, {settings.DS_POWER_MAX}]",
                )
                if aid:
                    fired.append({"id": aid, "severity": "warn",
                        "message": f"DS ch{cid} power {ch.power_dbmv:.1f} dBmV OOR"})
            else:
                await _resolve_alert(db, f"ds_power_{cid}")

        uncorr_sev = None
        if ch.uncorrectables >= settings.UNCORRECTABLE_CRIT:
            uncorr_sev = "critical"
        elif ch.uncorrectables >= settings.UNCORRECTABLE_WARN:
            uncorr_sev = "warn"

        if uncorr_sev:
            aid = await _open_alert(
                db, f"ds_uncorr_{cid}", uncorr_sev, cid,
                "uncorrectables", float(ch.uncorrectables),
                float(settings.UNCORRECTABLE_WARN),
                f"DS ch{cid}: {ch.uncorrectables} uncorrectable errors",
            )
            if aid:
                fired.append({"id": aid, "severity": uncorr_sev,
                    "message": f"DS ch{cid} uncorrectables: {ch.uncorrectables}"})
        else:
            await _resolve_alert(db, f"ds_uncorr_{cid}")

    # Upstream
    for ch in snap.upstream:
        cid = ch.channel_id or 0

        if ch.power_dbmv is not None:
            if not (settings.US_POWER_MIN <= ch.power_dbmv <= settings.US_POWER_MAX):
                aid = await _open_alert(
                    db, f"us_power_{cid}", "warn", cid, "power_dbmv",
                    ch.power_dbmv, None,
                    f"US ch{cid}: power {ch.power_dbmv:.1f} dBmV outside "
                    f"[{settings.US_POWER_MIN}, {settings.US_POWER_MAX}]",
                )
                if aid:
                    fired.append({"id": aid, "severity": "warn",
                        "message": f"US ch{cid} power {ch.power_dbmv:.1f} dBmV OOR"})
            else:
                await _resolve_alert(db, f"us_power_{cid}")

        t3t4 = ch.t3_timeouts + ch.t4_timeouts
        if t3t4 >= settings.T3_T4_CRIT_COUNT:
            aid = await _open_alert(
                db, f"us_t3t4_{cid}", "critical", cid,
                "t3t4_timeouts", float(t3t4), float(settings.T3_T4_CRIT_COUNT),
                f"US ch{cid}: T3={ch.t3_timeouts} T4={ch.t4_timeouts} — ranging instability",
            )
            if aid:
                fired.append({"id": aid, "severity": "critical",
                    "message": f"US ch{cid} T3/T4: {t3t4}"})
        else:
            await _resolve_alert(db, f"us_t3t4_{cid}")

    if fired:
        await _dispatch_notifications(snap, fired)
    return fired


# Notification dispatch

def _webhook_payload(snap: RouterSnapshot, alerts: list[dict]) -> dict:
    return {
        "source": "docsis-monitor",
        "router_ip": settings.ROUTER_IP,
        "polled_at": snap.polled_at.isoformat() + "Z",
        "alert_count": len(alerts),
        "alerts": [{"id": a["id"], "severity": a["severity"],
                    "message": a["message"]} for a in alerts],
        "wan_ip": snap.wan_ip,
        "router_up": snap.router_up,
    }


def _slack_payload(snap: RouterSnapshot, alerts: list[dict]) -> dict:
    crit  = [a for a in alerts if a["severity"] == "critical"]
    color = "#FF0000" if crit else "#FFA500"
    lines = "\n".join(f"• [{a['severity'].upper()}] {a['message']}" for a in alerts)
    return {
        "attachments": [{
            "color": color,
            "title": f"🚨 DOCSIS Monitor — {len(alerts)} alert(s)",
            "text": lines,
            "footer": f"Router {settings.ROUTER_IP} | "
                      f"{snap.polled_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "fields": [
                {"title": "Critical", "value": str(len(crit)), "short": True},
                {"title": "Warning",  "value": str(len(alerts) - len(crit)), "short": True},
            ],
        }]
    }


def _discord_payload(snap: RouterSnapshot, alerts: list[dict]) -> dict:
    crit = any(a["severity"] == "critical" for a in alerts)
    return {
        "username": "DOCSIS Monitor",
        "embeds": [{
            "title": f"{'🔴' if crit else '🟡'} DOCSIS Alert — {len(alerts)} issue(s)",
            "color": 16711680 if crit else 16753920,
            "description": "\n".join(
                f"**[{a['severity'].upper()}]** {a['message']}" for a in alerts
            ),
            "footer": {"text": f"Router {settings.ROUTER_IP}"},
            "timestamp": snap.polled_at.isoformat() + "Z",
        }],
    }


async def _send_webhook(url: str, snap: RouterSnapshot, alerts: list[dict]):
    if "slack.com" in url:
        payload = _slack_payload(snap, alerts)
    elif "discord.com" in url:
        payload = _discord_payload(snap, alerts)
    else:
        payload = _webhook_payload(snap, alerts)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            (await client.post(url, json=payload)).raise_for_status()
        log.info("alerting.webhook_sent", url=url[:50])
    except Exception as e:
        log.error("alerting.webhook_failed", url=url[:50], error=str(e))


async def _send_email(snap: RouterSnapshot, alerts: list[dict]):
    if not all([settings.SMTP_HOST, settings.SMTP_TO]):
        return
    lines = [f"DOCSIS Monitor — {snap.polled_at.strftime('%Y-%m-%d %H:%M UTC')}", ""]
    for a in alerts:
        lines.append(f"[{a['severity'].upper()}] {a['message']}")
    lines += ["", f"Router: {settings.ROUTER_IP}", f"WAN IP: {snap.wan_ip or 'unknown'}"]
    msg = EmailMessage()
    msg["Subject"] = f"[DOCSIS Monitor] {len(alerts)} alert(s)"
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = settings.SMTP_TO
    msg.set_content("\n".join(lines))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
            srv.starttls(context=ctx)
            if settings.SMTP_USER:
                srv.login(settings.SMTP_USER, settings.SMTP_PASS or "")
            srv.send_message(msg)
    except Exception as e:
        log.error("alerting.email_failed", error=str(e))


async def _dispatch_notifications(snap: RouterSnapshot, alerts: list[dict]):
    tasks = [_send_webhook(u, snap, alerts) for u in settings.webhook_list]
    tasks.append(_send_email(snap, alerts))
    await asyncio.gather(*tasks, return_exceptions=True)
