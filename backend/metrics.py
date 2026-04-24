from prometheus_client import (
    Gauge, Counter, CollectorRegistry,
    generate_latest, CONTENT_TYPE_LATEST,
)

registry = CollectorRegistry()

ds_power  = Gauge("docsis_downstream_power_dbmv",      "DS power (dBmV)",     ["channel_id","docsis_version"], registry=registry)
ds_snr    = Gauge("docsis_downstream_snr_db",          "DS SNR (dB)",         ["channel_id","docsis_version"], registry=registry)
ds_uncorr = Gauge("docsis_downstream_uncorrectables",  "DS uncorrectables",   ["channel_id"], registry=registry)
ds_corr   = Gauge("docsis_downstream_corrected",       "DS corrected",        ["channel_id"], registry=registry)
ds_locked = Gauge("docsis_downstream_locked",          "DS locked (1=yes)",   ["channel_id"], registry=registry)
us_power  = Gauge("docsis_upstream_power_dbmv",        "US power (dBmV)",     ["channel_id","docsis_version"], registry=registry)
us_t3     = Gauge("docsis_upstream_t3_timeouts",       "US T3 timeouts",      ["channel_id"], registry=registry)
us_t4     = Gauge("docsis_upstream_t4_timeouts",       "US T4 timeouts",      ["channel_id"], registry=registry)
router_up = Gauge("docsis_router_up",                  "Router up (1=yes)",   registry=registry)
poll_total  = Counter("docsis_poll_total",             "Total polls",         registry=registry)
poll_errors = Counter("docsis_poll_errors_total",      "Failed polls",        registry=registry)
alert_total = Counter("docsis_alerts_total",           "Alerts fired",        ["severity"], registry=registry)


def update_metrics(snap) -> None:
    poll_total.inc()
    router_up.set(1 if snap.router_up else 0)
    if not snap.router_up:
        poll_errors.inc()
        return
    for ch in snap.downstream:
        cid, ver = str(ch.channel_id or "?"), ch.docsis_version
        if ch.power_dbmv is not None:
            ds_power.labels(channel_id=cid, docsis_version=ver).set(ch.power_dbmv)
        if ch.snr_db is not None:
            ds_snr.labels(channel_id=cid, docsis_version=ver).set(ch.snr_db)
        ds_uncorr.labels(channel_id=cid).set(ch.uncorrectables)
        ds_corr.labels(channel_id=cid).set(ch.corrected)
        ds_locked.labels(channel_id=cid).set(
            1 if ch.lock_status and "locked" in ch.lock_status.lower() else 0
        )
    for ch in snap.upstream:
        cid, ver = str(ch.channel_id or "?"), ch.docsis_version
        if ch.power_dbmv is not None:
            us_power.labels(channel_id=cid, docsis_version=ver).set(ch.power_dbmv)
        us_t3.labels(channel_id=cid).set(ch.t3_timeouts)
        us_t4.labels(channel_id=cid).set(ch.t4_timeouts)


def get_metrics_output() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
