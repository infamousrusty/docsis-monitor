# hello-world

A minimal, production-grade boilerplate for containerised applications
with supply chain security built in.

A GitHub template repository providing a ready-to-use foundation with:

- Immutable image builds — tagged by commit SHA, pushed to GHCR
- Keyless cosign signing — OIDC via Sigstore/Fulcio, recorded in Rekor
- SLSA provenance attestation — provenance: mode=max via BuildKit
- SBOM generation — attached as OCI layer at build time
- Dependabot — weekly Actions update PRs

---

## Using This Template

1. Click Use this template -> Create a new repository
2. Clone your new repo
3. Replace .devcontainer/Dockerfile with your own
4. Push to main — the pipeline runs automatically

---

## Repository Structure

.
├── .devcontainer/
│   └── Dockerfile                  # Container definition
├── .github/
│   ├── dependabot.yml              # Weekly Actions update PRs
│   └── workflows/
│       └── build-sign-attest.yml   # Build, Sign & Attest pipeline
├── LICENSE
└── README.md

---

## CI/CD Pipeline

Runs on every push to main and on v* tags.

Step              | Action                               | Output
------------------|--------------------------------------|----------------------------------------
Checkout          | actions/checkout@v4                  | Source on runner
Build & Push      | docker/build-push-action@v6          | Image at ghcr.io/<repo>:<sha>
Sign              | cosign sign                          | Keyless signature in GHCR + Rekor
Attest            | actions/attest-build-provenance@v3   | SLSA provenance
Summary           | Bash                                 | Build summary in Actions UI

---

## Verifying an Image

cosign verify \
  --certificate-identity-regexp="https://github.com/infamousrusty/hello-world/.*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/infamousrusty/hello-world@sha256:<digest>

---

## Customising

File                                       | What to change
-------------------------------------------|--------------------------------
.devcontainer/Dockerfile                   | Your application container
.github/workflows/build-sign-attest.yml    | Tags, platforms, extra steps
.github/dependabot.yml                     | Schedule, labels, PR limits

---

## License

MIT (c) Anton-Curtis Cooper / Infamous