#!/usr/bin/env bash
set -euo pipefail

GREEN="\u001B[0;32m"; CYAN="\u001B[0;36m"; BOLD="\u001B[1m"; RESET="\u001B[0m"
info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}   $*"; }

echo -e "${BOLD}Bootstrap: DevSecOps Repository${RESET}"

command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }

info "Installing pre-commit..."
pip install --quiet pre-commit
pre-commit install --install-hooks
pre-commit install --hook-type commit-msg
success "pre-commit hooks installed"

info "Installing Python tooling..."
pip install --quiet ruff black pytest pytest-cov yamllint mkdocs-material
success "Python tooling installed"

if command -v npm >/dev/null 2>&1; then
  [[ -f "package.json" ]] && npm ci --prefer-offline --silent || true
  npm install -g --ignore-scripts prettier markdownlint-cli2 --silent 2>/dev/null || true
  success "Node.js tooling installed"
fi

[[ -f ".env" ]] || { cp .env.example .env; success ".env created from .env.example"; }

echo -e "
${GREEN}✔ Bootstrap complete${RESET}"
echo -e "  Run ${CYAN}make lint${RESET} to validate"
echo -e "  Run ${CYAN}make test${RESET} to run tests"
echo -e "  Run ${CYAN}./scripts/ci-local.sh${RESET} for full CI"