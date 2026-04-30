# Changelog

## 1.0.0 (2026-04-30)


### Features

* add CI pipeline, nginx hardening, grafana provisioning, test suite, deployment tooling ([7b94fc0](https://github.com/infamousrusty/docsis-monitor/commit/7b94fc09708a959f72ad541000d02dd4d9a5124b))
* add complete DOCSIS monitor stack - backend, frontend, nginx, grafana ([45f4c7c](https://github.com/infamousrusty/docsis-monitor/commit/45f4c7c9882fb0e44dc82960735a6aacfbae4267))
* add docker-compose, prometheus config, nginx, CI workflow ([9bbacc7](https://github.com/infamousrusty/docsis-monitor/commit/9bbacc7bd345695945eedbdf327664f4d4036314))
* add grafana provisioning, dashboard, and deployment readiness fixes ([87327f5](https://github.com/infamousrusty/docsis-monitor/commit/87327f5e8b9407190ad6b858a888b205ad33aae5))
* add scraper, alerting, diagnostics, metrics, main ([cf2a5ec](https://github.com/infamousrusty/docsis-monitor/commit/cf2a5ec5fd4f2eea46731ea28ad20b9685b1114d))
* **backend:** push complete production backend — scraper, alerting, diagnostics, metrics, API ([078c801](https://github.com/infamousrusty/docsis-monitor/commit/078c80115cd5341871b0598119e87b479f784311))
* **backend:** push complete production backend stack ([27f5dce](https://github.com/infamousrusty/docsis-monitor/commit/27f5dce86a785fbf3a7e86fc8e2b4650a211ff59))
* **ci:** add pytest+Trivy+ruff CI pipeline with mock router fixtures ([a5e320a](https://github.com/infamousrusty/docsis-monitor/commit/a5e320a73b02696d054d7eb2061163cde51174a5))
* **core:** implement full DOCSIS monitoring stack ([006886d](https://github.com/infamousrusty/docsis-monitor/commit/006886df348caa589c2108d2e709c79c47f06883))
* **frontend:** add complete multi-page dashboard UI ([b46ff9e](https://github.com/infamousrusty/docsis-monitor/commit/b46ff9e3404e4e5e4856e0d006ce5cb45a476f60))
* **grafana:** add Prometheus provisioning and pre-built DOCSIS dashboard ([2911bb5](https://github.com/infamousrusty/docsis-monitor/commit/2911bb5f51ad79c3689e36f1d90c7c3db7ef4478))
* initial commit — DOCSIS monitor stack (FastAPI + SQLite + nginx + Prometheus + Grafana) ([6c3dad9](https://github.com/infamousrusty/docsis-monitor/commit/6c3dad9d4cf86cf0dd415f26efc051f5537c381e))
* **nginx:** production-hardened reverse proxy with rate-limiting and optional basic auth ([c0ac063](https://github.com/infamousrusty/docsis-monitor/commit/c0ac06362bda86e94f7affb31e0b18f3ee4900a5))
* push complete DOCSIS monitor stack (backend, frontend, nginx, compose, prometheus) ([eb7dc5e](https://github.com/infamousrusty/docsis-monitor/commit/eb7dc5ed6072f33797ec91dcd1c453ca7c69c551))


### Bug Fixes

* **backend:** add missing urllib3 dependency to requirements.txt ([5034b8c](https://github.com/infamousrusty/docsis-monitor/commit/5034b8c7b3079fe1e81b8d516778c08d7646c775))
* disable SSL verification for Hub 5 self-signed cert, default scheme to HTTPS ([91587f3](https://github.com/infamousrusty/docsis-monitor/commit/91587f32403649f477ebb1b75ce1d594e9af7076))
* **grafana:** copy dashboard JSON into image and add grafana to nginx depends_on ([4f72705](https://github.com/infamousrusty/docsis-monitor/commit/4f72705307b66e2c7b417894073778cde02c3861))
* **nginx:** remove build-time nginx -t — upstreams not resolvable during docker build ([9f00a7a](https://github.com/infamousrusty/docsis-monitor/commit/9f00a7a01a6efc1c4c0450766f735775362b494b))
* replace all bind-mounts with baked-in images + Portainer named volumes ([df9d208](https://github.com/infamousrusty/docsis-monitor/commit/df9d208143bd6636cae9b080827e44a7a878a5a9))
* resolve all 83 ruff errors (I001, F401, UP006/7/35, E501, S608, B905, C408, E741, W292) ([e6c879c](https://github.com/infamousrusty/docsis-monitor/commit/e6c879ccc5bb990f1bf88cc34ec60b3ebcab7444))
* resolve Portainer file bind-mount OCI error for Prometheus config ([12424f7](https://github.com/infamousrusty/docsis-monitor/commit/12424f7888cbb14ed2ee845b851f2842d6da7272))
