#!/usr/bin/env bash
set -euo pipefail

GREEN="\u001B[0;32m"; CYAN="\u001B[0;36m"; YELLOW="\u001B[0;33m"
RED="\u001B[0;31m"; BOLD="\u001B[1m"; RESET="\u001B[0m"

SKIP_SECURITY=false
[[ "${1:-}" == "--skip-security" ]] && SKIP_SECURITY=true

FAILED=()
run() {
  local name="$1"; shift
  echo -e "
${BOLD}${CYAN}▶ $name${RESET}"
  if "$@"; then echo -e "${GREEN}✔ $name${RESET}"
  else echo -e "${YELLOW}⚠ $name FAILED${RESET}"; FAILED+=("$name"); fi
}

echo -e "${BOLD}╔══════════════════════════╗${RESET}"
echo -e "${BOLD}║  Local CI Runner         ║${RESET}"
echo -e "${BOLD}╚══════════════════════════╝${RESET}"

run "Pre-commit" pre-commit run --all-files
command -v shellcheck >/dev/null && run "ShellCheck" bash -c 'find scripts -name "*.sh" -exec shellcheck --severity=warning {} +' || true
command -v hadolint >/dev/null && run "Hadolint" bash -c 'find . -name "Dockerfile*" -not -path "./.git/*" -exec hadolint {} ;' || true
command -v pytest >/dev/null && run "Pytest" pytest tests/ -v --tb=short --cov=src --cov-fail-under=80 || true

if [[ "$SKIP_SECURITY" == "false" ]]; then
  command -v gitleaks >/dev/null && run "Gitleaks" gitleaks detect --source . --config .gitleaks.toml || true
  command -v trivy >/dev/null && run "Trivy" trivy fs --exit-code 1 --severity HIGH,CRITICAL . || true
fi

echo -e "
${BOLD}══ CI Summary ══${RESET}"
if [[ ${#FAILED[@]} -eq 0 ]]; then echo -e "${GREEN}✔ All steps passed${RESET}"
else
  echo -e "${RED}✘ Failed:${RESET}"
  for s in "${FAILED[@]}"; do echo -e "  • $s"; done
  exit 1
fi