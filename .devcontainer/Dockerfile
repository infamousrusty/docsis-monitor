# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.11
ARG DEBIAN_CODENAME=bookworm

FROM python:${PYTHON_VERSION}-slim-${DEBIAN_CODENAME} AS base

ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="DevSecOps DevContainer" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git ca-certificates make shellcheck jq openssh-client gnupg2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Pull gitleaks binary from its official image ──────────────────────────────
FROM ghcr.io/gitleaks/gitleaks:v8.30.1 AS gitleaks

# ── Tooling stage ─────────────────────────────────────────────────────────────
FROM base AS tooling

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/gitleaks

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://aquasecurity.github.io/trivy-repo/deb/public.key \
        | gpg --dearmor -o /usr/share/keyrings/trivy.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" \
        > /etc/apt/sources.list.d/trivy.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends trivy \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        hadolint-bin==2.12.0 \
        pre-commit==3.7.1 ruff==0.4.4 black==24.4.2 yamllint==1.35.1 \
        pytest==8.2.1 pytest-cov==5.0.0 \
        mkdocs-material==9.5.25 mkdocs-git-revision-date-localized-plugin==1.2.5 \
    && npm install -g --ignore-scripts \
        prettier@3.3.0 markdownlint-cli2@0.13.0 \
        @commitlint/cli@19.3.0 @commitlint/config-conventional@19.2.2

# ── Final non-root stage ──────────────────────────────────────────────────────
FROM tooling AS final

ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" \
       --shell /bin/bash --create-home "${USERNAME}"

WORKDIR /workspace
RUN chown "${USER_UID}:${USER_GID}" /workspace

USER ${USERNAME}
ENTRYPOINT ["/bin/bash"]