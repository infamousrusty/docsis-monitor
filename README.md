# DOCSIS Monitor

Production-grade self-hosted monitoring stack for the **Virgin Media SuperHub 5** (DOCSIS 3.0/3.1).

## Features

- Polls Hub 5 CGI endpoints every 30 s (configurable)
- Parses downstream/upstream channel metrics, event logs, WAN status
- Multi-page web dashboard: Overview · Downstream · Upstream · Logs · Diagnostics
- Alert engine with debouncing — Slack, Discord, custom webhook, SMTP
- Historical trend graphs (Chart.js) — SNR, power, uncorrectables
- Prometheus `/metrics` endpoint + Grafana provisioned dashboard
- SQLite persistence with configurable retention (default 90 days)
- Fully Dockerised — compatible with Portainer

## Quick Start

```bash
git clone https://github.com/infamousrusty/docsis-monitor.git
cd docsis-monitor
cp .env.example .env
# Edit .env — set ROUTER_IP and optionally WEBHOOK_URLS
docker compose up -d
```

Open **http://localhost:3000** (or `EXPOSE_PORT` you set).

## Services

| Service | Port (internal) | Purpose |
|---|---|---|
| `app` | 8000 | FastAPI backend + polling engine |
| `web` | 80 | Static frontend (nginx) |
| `nginx` | `EXPOSE_PORT` (3000) | Reverse proxy, rate limiting |
| `prometheus` | 9090 | Metrics scraping |
| `grafana` | 3000 (internal) | `/grafana` sub-path |

## Alert Thresholds (defaults)

| Metric | Warning | Critical |
|---|---|---|
| DS SNR | < 33 dB | < 30 dB |
| DS Power | outside −7…+7 dBmV | — |
| US Power | outside 38…48.5 dBmV | — |
| Uncorrectables | > 100 | > 500 |
| T3/T4 Timeouts | — | ≥ 1 |

All thresholds are overridable via `.env`.

## Webhook Payload Example

```json
{
  "source": "docsis-monitor",
  "router_ip": "192.168.100.1",
  "polled_at": "2026-04-24T20:00:00Z",
  "alert_count": 1,
  "alerts": [
    { "id": 42, "severity": "critical", "message": "DS ch5 SNR 28.3 dB" }
  ],
  "wan_ip": "1.2.3.4",
  "router_up": true
}
```

## Environment Variables

See [`.env.example`](.env.example) for the full annotated reference.

## Router Mode vs Modem Mode

| Mode | Default IP | Notes |
|---|---|---|
| Modem/bridge | `192.168.100.1` | Set `ROUTER_IP=192.168.100.1` |
| Router mode | `192.168.0.1` | Set `ROUTER_IP=192.168.0.1` |

## License

MIT — see [LICENSE](LICENSE).
