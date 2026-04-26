"""
Unit tests for the alerting engine.
Verifies threshold evaluation, alert creation, and debounce logic.
"""
import asyncio
from datetime import datetime

import pytest
import pytest_asyncio

from alerting import evaluate_snapshot, _debounce
from models import RouterSnapshot, DownstreamChannel, UpstreamChannel


def _make_snap(**kwargs) -> RouterSnapshot:
    defaults = dict(
        polled_at=datetime.utcnow(),
        router_up=True,
        wan_ip="82.132.45.67",
        uptime_secs=86400,
        downstream=[],
        upstream=[],
        event_logs=[],
    )
    defaults.update(kwargs)
    return RouterSnapshot(**defaults)


@pytest.mark.asyncio
async def test_no_alerts_on_healthy_snapshot(db):
    snap = _make_snap(
        downstream=[
            DownstreamChannel(channel_id=1, power_dbmv=2.0, snr_db=38.0, uncorrectables=0)
        ],
        upstream=[
            UpstreamChannel(channel_id=1, power_dbmv=43.0, t3_timeouts=0, t4_timeouts=0)
        ],
    )
    alerts = await evaluate_snapshot(db, snap)
    assert alerts == []


@pytest.mark.asyncio
async def test_router_down_fires_critical(db):
    _debounce.clear()
    snap = _make_snap(router_up=False)
    alerts = await evaluate_snapshot(db, snap)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_snr_warn_threshold(db):
    _debounce.clear()
    snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=1, snr_db=31.5, power_dbmv=2.0)]
    )
    alerts = await evaluate_snapshot(db, snap)
    sev = [a["severity"] for a in alerts]
    assert "warn" in sev
    assert "critical" not in sev


@pytest.mark.asyncio
async def test_snr_critical_threshold(db):
    _debounce.clear()
    snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=1, snr_db=28.0, power_dbmv=2.0)]
    )
    alerts = await evaluate_snapshot(db, snap)
    sev = [a["severity"] for a in alerts]
    assert "critical" in sev


@pytest.mark.asyncio
async def test_power_oor_fires_warn(db):
    _debounce.clear()
    snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=2, snr_db=38.0, power_dbmv=-9.0)]
    )
    alerts = await evaluate_snapshot(db, snap)
    assert any("power" in a["message"].lower() for a in alerts)


@pytest.mark.asyncio
async def test_high_uncorrectables_fires_crit(db):
    _debounce.clear()
    snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=3, snr_db=38.0, power_dbmv=2.0, uncorrectables=600)]
    )
    alerts = await evaluate_snapshot(db, snap)
    crit_alerts = [a for a in alerts if a["severity"] == "critical"]
    assert len(crit_alerts) >= 1


@pytest.mark.asyncio
async def test_t3_timeout_fires_critical(db):
    _debounce.clear()
    snap = _make_snap(
        upstream=[UpstreamChannel(channel_id=1, power_dbmv=43.0, t3_timeouts=3, t4_timeouts=0)]
    )
    alerts = await evaluate_snapshot(db, snap)
    assert any(a["severity"] == "critical" for a in alerts)


@pytest.mark.asyncio
async def test_debounce_prevents_duplicate_alert(db):
    """Second identical snapshot within debounce window must not re-fire."""
    _debounce.clear()
    snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=1, snr_db=28.0, power_dbmv=2.0)]
    )
    first  = await evaluate_snapshot(db, snap)
    second = await evaluate_snapshot(db, snap)
    assert len(first) >= 1
    # Same alert key is in debounce map → second call produces nothing new
    assert len(second) == 0


@pytest.mark.asyncio
async def test_alert_resolves_when_metric_recovers(db):
    _debounce.clear()
    bad_snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=1, snr_db=28.0, power_dbmv=2.0)]
    )
    await evaluate_snapshot(db, bad_snap)

    # Wipe debounce to simulate time passing
    _debounce.clear()

    good_snap = _make_snap(
        downstream=[DownstreamChannel(channel_id=1, snr_db=38.0, power_dbmv=2.0)]
    )
    alerts = await evaluate_snapshot(db, good_snap)
    # No new alerts on recovery — just resolution
    crit = [a for a in alerts if a["severity"] == "critical"]
    assert len(crit) == 0

    # Confirm the original alert is now resolved in the DB
    async with db.execute(
        "SELECT resolved_at FROM alerts WHERE alert_key='ds_snr_crit_1'"
    ) as cur:
        row = await cur.fetchone()
    assert row is not None
    assert row[0] is not None  # resolved_at populated
