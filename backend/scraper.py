"""
Hub 5 scraper — handles both router mode (192.168.0.1) and modem mode (192.168.100.1).
Endpoints discovered via community reverse engineering of VM Hub 5 firmware.
Gracefully degrades if any endpoint is unavailable.
"""
import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type,
)
import structlog

from config import settings
from models import RouterSnapshot, DownstreamChannel, UpstreamChannel, EventLogEntry

# The Hub 5 uses a self-signed certificate — suppress the per-request warning
# that urllib3 would otherwise emit. This is intentional: the device is
# LAN-only (192.168.100.1 / 192.168.0.1) so there is no MITM risk.

log = structlog.get_logger()

# Hub 5 CGI endpoints (modem + router mode)
EP_DOWNSTREAM = "/cgi-bin/VmRouterStatusDownstreamCfgCgi"
EP_UPSTREAM   = "/cgi-bin/VmRouterStatusUpstreamCfgCgi"
EP_EVENT_LOG  = "/cgi-bin/VmRouterEventLogCgi"
EP_WAN        = "/cgi-bin/VmRouterStatusWanCgi"
EP_STATUS     = "/cgi-bin/VmRouterStatusCgi"

# Fallback endpoints for alternate firmware versions
EP_DS_ALT     = "/docsis_status.asp"
EP_US_ALT     = "/docsis_status.asp"
EP_LOG_ALT    = "/network_log.asp"


def _make_client() -> httpx.AsyncClient:
    """
    Build the shared httpx client for all Hub 5 requests.

    SSL verification is disabled (verify=False) because the Hub 5 firmware
    serves HTTPS with a self-signed certificate that cannot be added to the
    system trust store from inside the container. This is safe for a
    LAN-only management interface.
    """
    kwargs: dict = dict(
        base_url=settings.router_base_url,
        timeout=settings.REQUEST_TIMEOUT,
        follow_redirects=True,
        verify=False,
        headers={"User-Agent": "DOCSIS-Monitor/1.0"},
    )
    if settings.ROUTER_USER and settings.ROUTER_PASS:
        kwargs["auth"] = (settings.ROUTER_USER, settings.ROUTER_PASS)
    return httpx.AsyncClient(**kwargs)


@retry(
    stop=stop_after_attempt(settings.REQUEST_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=False,
)
async def _fetch(client: httpx.AsyncClient, path: str) -> Optional[str]:
    try:
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        log.warning("scraper.http_error", path=path, status=e.response.status_code)
        return None
    except Exception as e:
        log.warning("scraper.fetch_failed", path=path, error=str(e))
        return None


def _col_values(soup: BeautifulSoup, label: str) -> list[str]:
    """Find a table row by its first-cell text, return remaining cells."""
    cell = soup.find(string=re.compile(r"^\s*" + re.escape(label) + r"\s*$"))
    if not cell:
        return []
    row = cell.find_parent("tr")
    if not row:
        return []
    cells = row.find_all("td")
    return [c.get_text(strip=True) for c in cells[1:]]


def _sf(val: str) -> Optional[float]:
    try:
        return float(re.sub(r"[^\d.\-]", "", val.replace("N/A", "").strip()))
    except (ValueError, AttributeError):
        return None


def _si(val: str) -> Optional[int]:
    try:
        return int(re.sub(r"[^\d]", "", val.replace("N/A", "").strip()))
    except (ValueError, AttributeError):
        return None


def _g(lst: list, idx: int) -> str:
    return lst[idx] if idx < len(lst) else ""


def parse_downstream(html: str) -> list[DownstreamChannel]:
    soup = BeautifulSoup(html, "lxml")
    chan_ids  = _col_values(soup, "Channel ID")
    freqs     = _col_values(soup, "Frequency (Hz)")
    powers    = _col_values(soup, "Power Level (dBmV)")
    snrs      = _col_values(soup, "RxMER (dB)") or _col_values(soup, "SNR (dB)")
    mods      = _col_values(soup, "Modulation")
    locks     = _col_values(soup, "Lock Status")
    corrected = _col_values(soup, "Corrected") or _col_values(soup, "Pre RS Errors")
    uncorr    = _col_values(soup, "Uncorrectables") or _col_values(soup, "Post RS Errors")
    chan_types = _col_values(soup, "Channel Type")

    n = max(len(chan_ids), len(powers), 1)
    channels = []
    for i in range(n):
        docsis = "3.1" if "OFDM" in _g(chan_types, i).upper() else "3.0"
        channels.append(DownstreamChannel(
            channel_id=_si(_g(chan_ids, i)),
            frequency_hz=_si(_g(freqs, i)),
            power_dbmv=_sf(_g(powers, i)),
            snr_db=_sf(_g(snrs, i)),
            modulation=_g(mods, i) or None,
            lock_status=_g(locks, i) or None,
            corrected=_si(_g(corrected, i)) or 0,
            uncorrectables=_si(_g(uncorr, i)) or 0,
            docsis_version=docsis,
        ))
    return channels


def parse_upstream(html: str) -> list[UpstreamChannel]:
    soup = BeautifulSoup(html, "lxml")
    chan_ids = _col_values(soup, "Channel ID")
    freqs    = _col_values(soup, "Frequency (Hz)")
    powers   = _col_values(soup, "Power Level (dBmV)")
    types    = _col_values(soup, "Channel Type")
    t1 = _col_values(soup, "T1 Timeouts")
    t2 = _col_values(soup, "T2 Timeouts")
    t3 = _col_values(soup, "T3 Timeouts")
    t4 = _col_values(soup, "T4 Timeouts")

    n = max(len(chan_ids), len(powers), 1)
    channels = []
    for i in range(n):
        docsis = "3.1" if "SC-OFDMA" in _g(types, i).upper() else "3.0"
        channels.append(UpstreamChannel(
            channel_id=_si(_g(chan_ids, i)),
            frequency_hz=_si(_g(freqs, i)),
            power_dbmv=_sf(_g(powers, i)),
            channel_type=_g(types, i) or None,
            t1_timeouts=_si(_g(t1, i)) or 0,
            t2_timeouts=_si(_g(t2, i)) or 0,
            t3_timeouts=_si(_g(t3, i)) or 0,
            t4_timeouts=_si(_g(t4, i)) or 0,
            docsis_version=docsis,
        ))
    return channels


def parse_event_log(html: str) -> list[EventLogEntry]:
    soup = BeautifulSoup(html, "lxml")
    entries = []
    for row in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 3:
            continue
        message = cells[-1]
        if not message or message.lower() in ("description", "message", "event"):
            continue
        level = cells[2].upper() if len(cells) >= 3 else ""
        if "CRIT" in level or "EMERG" in level:
            severity, priority = "CRITICAL", 2
        elif "ERR" in level:
            severity, priority = "ERROR", 3
        elif "WARN" in level:
            severity, priority = "WARNING", 4
        else:
            severity, priority = "NOTICE", 5
        entries.append(EventLogEntry(
            ts=cells[0] or datetime.utcnow().isoformat() + "Z",
            priority=priority,
            severity=severity,
            message=message,
        ))
    return entries


def parse_wan_info(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    info: dict = {"wan_ip": None, "uptime_secs": None}
    for label in ("WAN IP Address", "IP Address", "IPv4 Address"):
        row = _col_values(soup, label)
        if row:
            info["wan_ip"] = row[0]
            break
    for label in ("System Up Time", "Uptime", "System Uptime"):
        row = _col_values(soup, label)
        if row:
            raw = row[0]
            total = 0
            dm = re.search(r"(\d+)\s*d", raw, re.I)
            if dm:
                total += int(dm.group(1)) * 86400
            hm = re.search(r"(\d+):(\d+):(\d+)", raw)
            if hm:
                total += int(hm.group(1)) * 3600 + int(hm.group(2)) * 60 + int(hm.group(3))
            info["uptime_secs"] = total or None
            break
    return info


async def poll_router() -> RouterSnapshot:
    polled_at = datetime.utcnow()
    async with _make_client() as client:
        ds_html, us_html, log_html, wan_html = await asyncio.gather(
            _fetch(client, EP_DOWNSTREAM),
            _fetch(client, EP_UPSTREAM),
            _fetch(client, EP_EVENT_LOG),
            _fetch(client, EP_WAN),
        )

    router_up = any([ds_html, us_html])
    snap = RouterSnapshot(
        polled_at=polled_at,
        router_up=router_up,
        downstream=parse_downstream(ds_html) if ds_html else [],
        upstream=parse_upstream(us_html) if us_html else [],
        event_logs=parse_event_log(log_html) if log_html else [],
        **(parse_wan_info(wan_html) if wan_html else {}),
    )
    log.info("scraper.poll", router_up=router_up,
             ds_channels=len(snap.downstream),
             us_channels=len(snap.upstream))
    return snap
