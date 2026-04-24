import aiosqlite


async def get_diagnostics(db: aiosqlite.Connection) -> dict:
    diags = {
        "signal_instability": [],
        "channel_imbalance": None,
        "high_uncorrectables": [],
        "t3t4_warnings": [],
        "snr_trend": {},
        "power_trend": {},
        "summary": "OK",
    }

    async with db.execute(
        "SELECT id FROM poll_snapshots WHERE router_up=1 ORDER BY ts DESC LIMIT 20"
    ) as cur:
        snap_ids = [row[0] for row in await cur.fetchall()]

    if not snap_ids:
        diags["summary"] = "UNKNOWN"
        return diags

    ph = ",".join("?" * len(snap_ids))

    async with db.execute(
        f"""SELECT channel_id, AVG(snr_db), MIN(snr_db), MAX(snr_db)
            FROM downstream_channels
            WHERE snapshot_id IN ({ph}) AND snr_db IS NOT NULL
            GROUP BY channel_id""",
        snap_ids,
    ) as cur:
        for cid, avg_s, min_s, max_s in await cur.fetchall():
            diags["snr_trend"][cid] = {
                "avg": round(avg_s, 2),
                "min": round(min_s, 2),
                "max": round(max_s, 2),
            }
            if avg_s and avg_s < 33:
                diags["signal_instability"].append({
                    "channel_id": cid,
                    "metric": "snr_db",
                    "avg": round(avg_s, 2),
                    "detail": f"Channel {cid} avg SNR {avg_s:.1f} dB \u2014 degraded",
                })

    async with db.execute(
        f"""SELECT channel_id, AVG(power_dbmv), MIN(power_dbmv), MAX(power_dbmv)
            FROM downstream_channels
            WHERE snapshot_id IN ({ph}) AND power_dbmv IS NOT NULL
            GROUP BY channel_id""",
        snap_ids,
    ) as cur:
        rows = await cur.fetchall()

    powers = []
    for cid, avg_p, min_p, max_p in rows:
        diags["power_trend"][cid] = {
            "avg": round(avg_p, 2),
            "min": round(min_p, 2),
            "max": round(max_p, 2),
        }
        if avg_p is not None:
            powers.append(avg_p)

    if len(powers) > 1:
        spread = max(powers) - min(powers)
        diags["channel_imbalance"] = {
            "spread_dbmv": round(spread, 2),
            "flagged": spread > 6.0,
            "detail": f"Power spread across {len(powers)} DS channels: {spread:.1f} dBmV",
        }

    async with db.execute(
        f"""SELECT channel_id, SUM(uncorrectables)
            FROM downstream_channels
            WHERE snapshot_id IN ({ph})
            GROUP BY channel_id HAVING SUM(uncorrectables) > 0
            ORDER BY SUM(uncorrectables) DESC""",
        snap_ids,
    ) as cur:
        for cid, total in await cur.fetchall():
            diags["high_uncorrectables"].append({
                "channel_id": cid,
                "total": total,
                "detail": f"Channel {cid}: {total} uncorrectables in last 20 polls",
            })

    async with db.execute(
        f"""SELECT channel_id, SUM(t3_timeouts), SUM(t4_timeouts)
            FROM upstream_channels
            WHERE snapshot_id IN ({ph})
            GROUP BY channel_id
            HAVING SUM(t3_timeouts)+SUM(t4_timeouts) > 0""",
        snap_ids,
    ) as cur:
        for cid, t3, t4 in await cur.fetchall():
            diags["t3t4_warnings"].append({
                "channel_id": cid,
                "t3_total": t3,
                "t4_total": t4,
                "detail": f"US ch{cid}: T3={t3} T4={t4} \u2014 ranging instability",
            })

    if diags["t3t4_warnings"]:
        diags["summary"] = "CRITICAL"
    elif diags["signal_instability"] or (
        diags["channel_imbalance"] and diags["channel_imbalance"]["flagged"]
    ):
        diags["summary"] = "WARNING"
    elif diags["high_uncorrectables"]:
        diags["summary"] = "WARNING"

    return diags


async def get_history(db: aiosqlite.Connection, metric: str, hours: int = 24) -> list[dict]:
    query_map = {
        "snr": """SELECT s.ts, d.channel_id, d.snr_db AS value
                  FROM downstream_channels d JOIN poll_snapshots s ON s.id=d.snapshot_id
                  WHERE s.ts >= datetime('now',?) ORDER BY s.ts, d.channel_id""",
        "ds_power": """SELECT s.ts, d.channel_id, d.power_dbmv AS value
                       FROM downstream_channels d JOIN poll_snapshots s ON s.id=d.snapshot_id
                       WHERE s.ts >= datetime('now',?) ORDER BY s.ts, d.channel_id""",
        "us_power": """SELECT s.ts, u.channel_id, u.power_dbmv AS value
                       FROM upstream_channels u JOIN poll_snapshots s ON s.id=u.snapshot_id
                       WHERE s.ts >= datetime('now',?) ORDER BY s.ts, u.channel_id""",
        "uncorrectables": """SELECT s.ts, d.channel_id, d.uncorrectables AS value
                             FROM downstream_channels d JOIN poll_snapshots s ON s.id=d.snapshot_id
                             WHERE s.ts >= datetime('now',?) ORDER BY s.ts, d.channel_id""",
    }
    sql = query_map.get(metric)
    if not sql:
        return []
    rows = []
    async with db.execute(sql, (f"-{hours} hours",)) as cur:
        async for row in cur:
            rows.append({"ts": row[0], "channel_id": row[1], "value": row[2]})
    return rows
