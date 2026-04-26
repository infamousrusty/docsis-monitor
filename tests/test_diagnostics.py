"""
Unit tests for the diagnostics engine.
Seeds the DB with synthetic snapshots and validates derived insights.
"""
import pytest
from datetime import datetime, timedelta

from diagnostics import get_diagnostics, get_history


async def _seed_snapshot(db, ts: str, ds_channels: list, us_channels: list):
    async with db.execute(
        "INSERT INTO poll_snapshots (ts, router_up) VALUES (?, 1)", (ts,)
    ) as cur:
        snap_id = cur.lastrowid
    for ch in ds_channels:
        await db.execute(
            """INSERT INTO downstream_channels
               (snapshot_id, channel_id, power_dbmv, snr_db, uncorrectables, corrected)
               VALUES (?,?,?,?,?,0)""",
            (snap_id, ch["id"], ch["power"], ch["snr"], ch.get("uncorr", 0)),
        )
    for ch in us_channels:
        await db.execute(
            """INSERT INTO upstream_channels
               (snapshot_id, channel_id, power_dbmv, t3_timeouts, t4_timeouts)
               VALUES (?,?,?,?,?)""",
            (snap_id, ch["id"], ch["power"], ch.get("t3", 0), ch.get("t4", 0)),
        )
    await db.commit()


@pytest.mark.asyncio
async def test_summary_ok_on_healthy_data(db):
    for i in range(5):
        ts = (datetime.utcnow() - timedelta(minutes=i * 5)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[{"id": 1, "power": 2.0, "snr": 38.0}],
            us_channels=[{"id": 1, "power": 43.0}],
        )
    result = await get_diagnostics(db)
    assert result["summary"] == "OK"
    assert result["signal_instability"] == []
    assert result["t3t4_warnings"] == []


@pytest.mark.asyncio
async def test_signal_instability_detected(db):
    for i in range(5):
        ts = (datetime.utcnow() - timedelta(minutes=i * 5)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[{"id": 1, "power": 2.0, "snr": 31.0}],  # below warn threshold
            us_channels=[{"id": 1, "power": 43.0}],
        )
    result = await get_diagnostics(db)
    assert result["summary"] in ("WARNING", "CRITICAL")
    assert len(result["signal_instability"]) >= 1
    assert result["signal_instability"][0]["channel_id"] == 1


@pytest.mark.asyncio
async def test_channel_imbalance_detected(db):
    for i in range(5):
        ts = (datetime.utcnow() - timedelta(minutes=i * 5)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[
                {"id": 1, "power": -8.0, "snr": 38.0},  # low power
                {"id": 2, "power":  0.0, "snr": 38.0},
                {"id": 3, "power":  5.0, "snr": 38.0},  # spread > 6 dBmV
            ],
            us_channels=[],
        )
    result = await get_diagnostics(db)
    assert result["channel_imbalance"] is not None
    assert result["channel_imbalance"]["flagged"] is True
    assert result["channel_imbalance"]["spread_dbmv"] > 6.0


@pytest.mark.asyncio
async def test_t3t4_warning_detected(db):
    for i in range(3):
        ts = (datetime.utcnow() - timedelta(minutes=i * 5)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[{"id": 1, "power": 2.0, "snr": 38.0}],
            us_channels=[{"id": 1, "power": 43.0, "t3": 2, "t4": 1}],
        )
    result = await get_diagnostics(db)
    assert result["summary"] == "CRITICAL"
    assert len(result["t3t4_warnings"]) >= 1
    tw = result["t3t4_warnings"][0]
    assert tw["t3_total"] == 6
    assert tw["t4_total"] == 3


@pytest.mark.asyncio
async def test_high_uncorrectables_reported(db):
    for i in range(3):
        ts = (datetime.utcnow() - timedelta(minutes=i * 5)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[{"id": 5, "power": -8.0, "snr": 29.0, "uncorr": 250}],
            us_channels=[],
        )
    result = await get_diagnostics(db)
    assert len(result["high_uncorrectables"]) == 1
    assert result["high_uncorrectables"][0]["total"] == 750


@pytest.mark.asyncio
async def test_history_returns_ordered_data(db):
    for i in range(3):
        ts = (datetime.utcnow() - timedelta(hours=i)).isoformat() + "Z"
        await _seed_snapshot(
            db, ts,
            ds_channels=[{"id": 1, "power": 2.0, "snr": 38.0 - i}],
            us_channels=[],
        )
    history = await get_history(db, "snr", hours=24)
    assert len(history) == 3
    assert all("ts" in r and "channel_id" in r and "value" in r for r in history)
