# Proxmox LXC Deployment — DOCSIS Monitor

This guide deploys the DOCSIS Monitor stack into a **Debian 12 (Bookworm) LXC container** on Proxmox VE 8.x.

---

## Container Spec

| Setting         | Recommended value       | Notes                                    |
|-----------------|-------------------------|------------------------------------------|
| Template        | debian-12-standard      | Proxmox CT template gallery              |
| CPU cores       | 2                       | 1 is fine; 2 for Prometheus + Grafana    |
| RAM             | 512 MB (hard) + 256 swap| Grafana spikes on first load             |
| Disk            | 8 GB                    | SQLite + Prometheus TSDB + Grafana       |
| Network         | bridge (vmbr0) + DHCP   | Or static VLAN for isolation             |
| Unprivileged    | **Yes**                 | Required; Docker nested in LXC needs key |
| Nesting feature | **Yes**                 | CT Options → Features → Nesting = ON     |
| Keyctl          | **Yes**                 | Required for Docker                      |

> **Security note**: running Docker inside an unprivileged LXC with nesting is acceptable for a home/homelab
> deployment. For higher-assurance environments, deploy on a dedicated lightweight VM (2 vCPU, 1 GB) instead.

---

## 1 · Create the Container

```bash
# On Proxmox host — adjust CTID, storage, and bridge to your site
pct create 120 \
  local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname docsis-monitor \
  --cores 2 \
  --memory 512 \
  --swap 256 \
  --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1,keyctl=1 \
  --start 1
```

---

## 2 · Bootstrap the Container

```bash
pct exec 120 -- bash -c "apt-get update && apt-get install -y curl git make"
```

### Install Docker (official script)

```bash
pct exec 120 -- bash -c "
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  usermod -aG docker root
"
```

---

## 3 · Deploy the Stack

```bash
pct exec 120 -- bash -c "
  git clone https://github.com/infamousrusty/docsis-monitor.git /opt/docsis-monitor
  cd /opt/docsis-monitor
  cp .env.example .env
  # Edit ROUTER_IP, WEBHOOK_URLS, GRAFANA_PASS etc.
  # nano .env
  make up
"
```

---

## 4 · Tailscale (Mesh Access)

Install Tailscale inside the LXC to make the dashboard accessible on your tailnet:

```bash
pct exec 120 -- bash -c "
  curl -fsSL https://tailscale.com/install.sh | sh
  tailscale up --hostname docsis-monitor --accept-routes
"
```

Then configure Tailscale Serve to proxy the dashboard over HTTPS on the tailnet:

```bash
pct exec 120 -- bash -c "
  tailscale serve --bg http://127.0.0.1:3000
"
```

Your dashboard will be available at `https://docsis-monitor.<tailnet>.ts.net` on all tailnet devices — 
no port forwarding, no public exposure, fully TLS-terminated by Tailscale.

---

## 5 · Auto-start on Proxmox Boot

```bash
# On Proxmox host
pct set 120 --onboot 1
```

The Docker daemon starts automatically via systemd inside the container.
Compose services restart via `restart: unless-stopped`.

---

## 6 · Resource Limits

Once running, trim the container if RAM is tight:

```bash
# Reduce Prometheus retention to save disk
# In docker-compose.yml, change:
#   --storage.tsdb.retention.time=90d
# to:
#   --storage.tsdb.retention.time=30d

# Check actual memory use
pct exec 120 -- bash -c "docker stats --no-stream"
```

---

## 7 · Router Reachability Check

The router (`192.168.100.1` in modem mode) must be reachable from inside the LXC.

```bash
pct exec 120 -- ping -c3 192.168.100.1
```

If using modem mode and the LXC is on a separate VLAN, add a static route:

```bash
# On the Proxmox host, persistent via /etc/network/interfaces
ip route add 192.168.100.0/24 via <your-gateway>
```

Or if the modem is directly bridged, ensure `vmbr0` or a dedicated bridge is on the same
layer-2 segment as the coax modem's management interface.

---

## Operational Notes

- **Backups**: `make backup-db` copies the SQLite file to `~/docsis-backups/`. Schedule via `cron` inside the LXC.
- **Updates**: `git pull && make build && make up` — Compose will roll the new images with zero manual steps.
- **Portainer**: navigate to `http://<lxc-ip>:9000` if you run Portainer alongside this stack (add it to `docker-compose.yml`).
