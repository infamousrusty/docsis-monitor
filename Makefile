# ──────────────────────────────────────────────────────────────────────────────
# DOCSIS Monitor — Makefile
# Usage: make <target>
# ──────────────────────────────────────────────────────────────────────────────
.PHONY: help up down restart logs status shell-app shell-db pull build \
        backup-db restore-db lint test clean trivy update-htpasswd

COMPOSE      := docker compose
APP          := docsis-app
DB_VOLUME    := docsis-monitor_db_data
BACKUP_DIR   := $(HOME)/docsis-backups
TIMESTAMP    := $(shell date +%Y%m%d-%H%M%S)

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-20s\033[0m %s\n",$$1,$$2}'

up:  ## Start all services (detached)
	$(COMPOSE) up -d --remove-orphans
	@echo "\n  Dashboard:  http://localhost:$${EXPOSE_PORT:-3000}/overview.html"
	@echo "  Grafana:    http://localhost:$${EXPOSE_PORT:-3000}/grafana/"
	@echo "  Health:     http://localhost:$${EXPOSE_PORT:-3000}/health\n"

down:  ## Stop and remove containers (preserves volumes)
	$(COMPOSE) down

restart:  ## Restart all services
	$(COMPOSE) restart

build:  ## (Re)build images from source
	$(COMPOSE) build --no-cache

pull:  ## Pull latest base images
	$(COMPOSE) pull

logs:  ## Follow logs for all services
	$(COMPOSE) logs -f --tail=100

logs-app:  ## Follow backend logs only
	$(COMPOSE) logs -f --tail=100 app

logs-nginx:  ## Follow nginx access logs
	$(COMPOSE) logs -f --tail=100 nginx

status:  ## Show service health
	$(COMPOSE) ps
	echo ""
	@curl -sf http://localhost:$${EXPOSE_PORT:-3000}/health | python3 -m json.tool || true

shell-app:  ## Open shell in the backend container
	$(COMPOSE) exec app /bin/bash

shell-nginx:  ## Open shell in nginx
	$(COMPOSE) exec nginx /bin/sh

# ── Database ──────────────────────────────────────────────────────────────────
backup-db:  ## Snapshot the SQLite DB to ~/docsis-backups/
	@mkdir -p $(BACKUP_DIR)
	$(COMPOSE) exec app sqlite3 /data/docsis.db ".backup '/data/docsis-backup.db'"
	docker cp $(APP):/data/docsis-backup.db $(BACKUP_DIR)/docsis-$(TIMESTAMP).db
	$(COMPOSE) exec app rm /data/docsis-backup.db
	@echo "Backup saved: $(BACKUP_DIR)/docsis-$(TIMESTAMP).db"
	restore-db:  ## Restore from a backup (BACKUP=path/to/file.db required)
restore-db:
	@test -n "$(BACKUP)" || (echo "Usage: make restore-db BACKUP=path/to/file.db" && exit 1)
	$(COMPOSE) stop app
	docker cp $(BACKUP) $(APP):/data/docsis.db
	$(COMPOSE) start app
	@echo "Restored from $(BACKUP)"

# ── Dev / CI ──────────────────────────────────────────────────────────────────
lint:  ## Run ruff lint + format check
	ruff check backend/ tests/
	ruff format --check backend/ tests/

test:  ## Run pytest suite
	cd backend && python -m pytest ../tests/ -v --tb=short

trivy:  ## Scan backend image for CVEs (requires Trivy installed)
	docker build -t docsis-app:local ./backend
	trivy image --severity CRITICAL,HIGH --ignore-unfixed docsis-app:local

# ── Security ──────────────────────────────────────────────────────────────────
update-htpasswd:  ## Regenerate basic auth credentials (USER=xxx PASS=xxx)
	@test -n "$(USER)" || (echo "Usage: make update-htpasswd USER=admin PASS=secret" && exit 1)
	@test -n "$(PASS)" || (echo "Usage: make update-htpasswd USER=admin PASS=secret" && exit 1)
	@mkdir -p nginx/auth
	@docker run --rm httpd:alpine htpasswd -Bbn $(USER) $(PASS) > nginx/auth/.htpasswd
	@echo "Written to nginx/auth/.htpasswd — restart nginx: make restart"

# ── Housekeeping ──────────────────────────────────────────────────────────────
clean:  ## Remove stopped containers and dangling images
	docker compose down --remove-orphans
	docker image prune -f
