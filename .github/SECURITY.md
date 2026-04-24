# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |
| < 1.0   | No        |

---

## Reporting a Vulnerability

Do NOT open a public GitHub issue for security vulnerabilities.

### GitHub Private Vulnerability Reporting (preferred)

1. Go to the Security tab -> Report a vulnerability
2. Fill in description, reproduction steps, and impact
3. We acknowledge within 48 hours, triage within 5 business days

### Encrypted Email (alternative)

Email security@infamous.is with subject: [SECURITY] Brief description

## Responsible Disclosure

- 90-day embargo before public disclosure
- Researchers credited in release notes (unless anonymity requested)
- No bug bounty programme at this time

---

## Supply Chain Security Controls

| Control             | Tool                          | Frequency              |
|---------------------|-------------------------------|------------------------|
| Keyless image signing | Sigstore cosign (OIDC)      | Every build            |
| Transparency log    | Rekor                         | Every build            |
| SLSA provenance     | BuildKit (mode=max)           | Every release          |
| SBOM                | CycloneDX via BuildKit        | Every release          |
| Immutable image refs | Digest-pinned tags           | Every build            |
| Secret scanning     | Gitleaks                      | Every commit + CI      |
| SAST                | CodeQL                        | Every PR + weekly      |
| Dependency CVEs     | Dependency Review + Trivy     | Every PR               |
| Container scanning  | Trivy                         | Every build            |
| Pinned Actions      | SHA-pinned workflows          | Always                 |
| Dependabot          | github-actions ecosystem      | Weekly                 |
| Signed commits      | GPG/SSH + branch protection   | Always                 |

---

## Verifying a Release

All images published by this repository are signed and can be independently verified.

Verify cosign signature:

  cosign verify \
    --certificate-identity-regexp="https://github.com/infamousrusty/hello-world/.*" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    ghcr.io/infamousrusty/hello-world@sha256:<digest>

Inspect SBOM attestation:

  cosign download attestation \
    ghcr.io/infamousrusty/hello-world@sha256:<digest> | jq .

Verify GitHub build provenance:

  gh attestation verify \
    --owner infamousrusty \
    oci://ghcr.io/infamousrusty/hello-world@sha256:<digest>