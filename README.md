# DOCSIS Monitor

Production-grade DOCSIS monitoring stack for the **Virgin Media SuperHub 5** (and compatible DOCSIS 3.0/3.1 modems).

[![CI](https://github.com/infamousrusty/docsis-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/infamousrusty/docsis-monitor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Features

- Continuous polling of SuperHub 5 internal CGI endpoints
- Parses DOCSIS 3.0 and 3.1 downstream/upstream channel metrics
- Multi-page web dashboard (Overview · Downstream · Upstream · Logs · Diagnostics)
- Threshold-based alerting via **Slack**, **Discord**, custom webhooks, and optional SMTP
- Debounced alert engine with severity classification
- SQLite persistence with configurable retention (default 90 days)
- Prometheus `/metrics` exporter
- Grafana dashboard provisioned automatically
- Fully Dockerised — deploy in under 5 minutes
- Portainer-compatible, zero cloud dependencies

---

## Quick Start

```bash
git clone https://github.com/infamousrusty/docsis-monitor.git
cd docsis-monitor
cp .env.example .env
# Edit .env — set ROUTER_IP and optionally WEBHOOK_URLS
docker compose up -d
```

Dashboard → `http://localhost:3000`  
Grafana → `http://localhost:3000/grafana`  
Prometheus → `http://localhost:9090` (internal only by default)

---

## Configuration

All configuration is via `.env`. Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `ROUTER_IP` | `192.168.100.1` | Hub 5 LAN IP (modem mode: 192.168.100.1, router mode: 192.168.0.1) |
| `POLL_INTERVAL` | `30` | Seconds between polls |
| `WEBHOOK_URLS` | `` | Comma-separated Slack/Discord/custom webhook URLs |
| `SNR_WARN_DB` | `33.0` | SNR warning threshold (dB) |
| `SNR_CRIT_DB` | `30.0` | SNR critical threshold (dB) |
| `DS_POWER_MIN` | `-7.0` | Downstream power floor (dBmV) |
| `DS_POWER_MAX` | `7.0` | Downstream power ceiling (dBmV) |
| `ALERT_DEBOUNCE_SECONDS` | `300` | Minimum seconds between repeated alert notifications |
| `DATA_RETENTION_DAYS` | `90` | Days of metric history to retain |
| `EXPOSE_PORT` | `3000` | Host port for the nginx reverse proxy |
| `GRAFANA_PASS` | `change-me-please` | Grafana admin password |

See `.env.example` for the full list.

---

## Architecture

```
┌─────────────┐     poll      ┌──────────────────┐
│  SuperHub 5 │◄──────────────│  app (FastAPI)   │
│ 192.168.x.x │               │  + APScheduler   │
└─────────────┘               └────────┬─────────┘
                                        │ writes
                               ┌────────▼─────────┐
                               │   SQLite /data   │
                               └────────┬─────────┘
                                        │ reads
┌──────────────┐  proxy   ┌────────────▼──────────┐
│   Browser    │◄─────────│   nginx (port 3000)   │
└──────────────┘          └──┬───────────┬────────┘
                              │           │
                    ┌─────────▼──┐  ┌────▼──────┐
                    │  web (UI)  │  │  Grafana  │
                    └────────────┘  └─────┬─────┘
                                          │
                                  ┌───────▼──────┐
                                  │  Prometheus  │
                                  └──────────────┘
```

---

## Alert Thresholds

| Metric | Warning | Critical |
|---|---|---|
| Downstream SNR | < 33 dB | < 30 dB |
| Downstream Power | outside −7 to +7 dBmV | — |
| Upstream Power | outside 38–48.5 dBmV | — |
| Uncorrectable Errors | > 100 | > 500 |
| T3/T4 Timeouts | — | any occurrence |
| Router Reachability | — | unreachable |

---

## Webhook Payloads

### Generic / Custom
```json
{
  "source": "docsis-monitor",
  "router_ip": "192.168.100.1",
  "polled_at": "2026-04-24T19:30:00Z",
  "alert_count": 2,
  "alerts": [
    {"id": 42, "severity": "critical", "message": "DS ch3 SNR 28.4 dB"},
    {"id": 43, "severity": "warn",     "message": "DS ch7 power 9.2 dBmV OOR"}
  ],
  "wan_ip": "81.109.x.x",
  "router_up": true
}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/overview` | Health summary + open alert counts |
| GET | `/api/v1/downstream` | Current DS channel data |
| GET | `/api/v1/upstream` | Current US channel data |
| GET | `/api/v1/logs` | Router event log (`?severity=CRITICAL&limit=200`) |
| GET | `/api/v1/diagnostics` | Derived health insights + trend data |
| GET | `/api/v1/alerts` | Alert history (`?open_only=true`) |
| GET | `/api/v1/history/{metric}` | Time-series data (`?hours=24`) |
| GET | `/api/v1/thresholds` | Active alert thresholds |
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition |

---

## Security

- No external exposure by default — nginx binds to localhost port 3000
- Optional HTTP Basic Auth via `BASIC_AUTH_USER` / `BASIC_AUTH_PASS`
- nginx rate limiting (10 req/s per IP, burst 20)
- All secrets via `.env` — never committed
- Non-root container user (`appuser`, UID 1001)
- Read-only nginx config mounts

---

## Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## License

[MIT](LICENSE) © 2026 infamousrusty
