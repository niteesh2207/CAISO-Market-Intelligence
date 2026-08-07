# CAISO Market Intelligence — V4.0.0

A **trust-first energy-market research API** that prioritizes official structured data, preserves source provenance, and uses controlled web research only when an approved structured executor is unavailable.

> **Status:** Public engineering alpha and portfolio demonstration. This repository is not a trading system, a replacement for licensed market-data services, or a guarantee that every energy question can be answered from a live structured source.

## Live analyst workspace

Open the private question-and-answer workspace:

**[Launch CAISO Market Intelligence Workspace](https://caiso-market-intelligence-workspace.mallavarapu-r.chatgpt.site)**

The hosted workspace routes questions to the V4 research API when a backend URL is configured, enables current source-grounded OpenAI research when a server-side key is configured, and otherwise remains useful through verified model evidence packs. Every path preserves source roles, limitations, and the prohibition on treating demonstration output as trading or settlement data.

## What is implemented

The V4 API currently provides:

- CAISO market-price research through a structured CAISO pathway;
- EIA Form EIA-930 operating-data research using a managed local cache;
- U.S. NRC reactor-status research;
- classification and routing across energy-market domains;
- primary/supporting source roles, confidence, limitations, and evidence payloads;
- clarification and hold states when mandatory evidence is incomplete;
- a controlled web-research fallback for routes without a connected structured executor;
- a credential-free public-web fallback that discovers approved sources,
  retrieves public pages safely, and returns cited evidence when no
  server-side OpenAI key is configured;
- FastAPI status, capability, search, and API-documentation endpoints;
- automated public-contract and unit tests.

## Trust model

The service follows this release sequence:

```text
Question
   ↓
Energy-domain classification
   ↓
Approved provider routing
   ↓
Structured executor, when available
   ↓
Evidence and freshness checks
   ↓
Answer / clarification / hold decision
   ↓
Optional controlled web fallback
```

A structured result remains the preferred evidence path. Web fallback is supporting research and is explicitly identified in the response; it is not presented as equivalent to a controlling settlement or operating-data feed.

## API surfaces

| Endpoint | Purpose |
|---|---|
| `GET /health` | Lightweight service and version check |
| `GET /api/status` | Runtime capability status |
| `GET /api/capabilities` | Implemented research capabilities |
| `POST /api/search` | Trust-first structured search with optional web fallback |
| `POST /api/ask` | Legacy authority-constrained web-research endpoint |
| `GET /docs` | OpenAPI documentation |

### Structured search example

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What were NP-15 day-ahead prices yesterday?",
    "allow_web_fallback": false
  }'
```

Set `allow_web_fallback` to `false` when the calling workflow requires a structured executor and should not accept web-research substitution.

With fallback enabled, a structured source outage no longer terminates the
request before research can run. The service logs the detailed executor error
server-side, then uses model-backed web research when `OPENAI_API_KEY` is
configured or deterministic source-grounded public research otherwise.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."  # required only for web-research endpoints
uvicorn app:app --reload
```

Open:

- application: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`

## Validate

```bash
pip install -r requirements-dev.txt
python -m compileall -q app.py market_intelligence scripts tests
python -m pytest
python -m ruff check app.py market_intelligence scripts tests
python scripts/validate_secret_scan.py
```

The GitHub Actions workflow repeats these checks for pull requests and changes to `main`.

## Public portfolio preview

The curated static preview is published through the least-privileged, SHA-pinned GitHub Pages workflow at:

`https://niteesh2207.github.io/CAISO-Market-Intelligence/`

The Pages artifact contains only `index.html`, the preview stylesheet and script, and the social-preview image. It performs no market-data requests, accepts no credentials, and does not expose the FastAPI backend. The preview and its deployment controls were verified on **August 6, 2026**.

## Data-source hierarchy

Source and acquisition rules were re-verified on **August 7, 2026**. See [`SOURCES.md`](SOURCES.md) for the controlling-source matrix, freshness gates, and the prohibition on scraping licensed or authenticated content.

### Controlling and authoritative sources

- California ISO OASIS and official CAISO publications
- U.S. Energy Information Administration
- U.S. Nuclear Regulatory Commission
- Federal Energy Regulatory Commission
- California Energy Commission and California Public Utilities Commission
- relevant balancing authorities, utilities, and government weather services

### Supporting sources

High-quality market reporting may be used for context, but should not replace a controlling official source for settlement, outage, operational, or regulatory claims when such a source exists.

### Premium and licensed data

This public repository does **not** bundle or redistribute licensed Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus, NGI, or private utility data. Premium integrations should use licensed APIs, bulk delivery, SFTP, or approved cloud delivery under the user's entitlements. Credentials and raw licensed datasets must remain outside the public repository.

## Security posture

- API credentials remain server-side.
- Raw internal exception messages are not returned to clients.
- The public alpha can run without application-level authentication; production deployments should enforce authentication, authorization, rate limits, request-size limits, audit logging, and network controls at the application gateway.
- Secrets must be stored in the deployment platform's secret manager, never in source control or browser code.
- Enable GitHub secret scanning, push protection, Dependabot, and branch protection before public promotion.

See [`SECURITY.md`](SECURITY.md) and [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md).

## Deployment

A Dockerfile and Render configuration are included. GitHub Pages can host only the static preview; it cannot safely host authenticated server-side research calls.

## Known limitations

- Some classified routes still return `research_required` because a live structured executor has not been connected.
- EIA operating-data results depend on cache availability and freshness.
- The web fallback depends on a configured OpenAI API key and should be treated as research support rather than a settlement-grade feed.
- The repository does not yet include application-level authentication, distributed rate limiting, production observability, or a service-level objective.

## Roadmap

### P0 — portfolio release

- keep V4 branding consistent across API, README, screenshots, and social preview;
- require CI on pull requests;
- publish a deterministic demonstration with stored response fixtures;
- document data freshness by metric and provider;
- configure repository security and branch protection.

### P1 — production hardening

- authenticated API access and rate limiting;
- structured outage, weather, regulatory, and gas-market connectors;
- persistent cache and evidence store;
- OpenTelemetry traces, structured logs, metrics, and alerting;
- contract tests against provider schemas.

### P2 — licensed enterprise deployment

- entitlement-aware premium data connectors;
- customer-specific access controls;
- reproducible research packets and audit exports;
- service-level objectives and incident runbooks.

## Intellectual property and disclaimer

The repository demonstrates system architecture and public-source research workflows. Proprietary ranking weights, commercial prompts, customer data, licensed datasets, and production trading logic should remain private.

This software is provided for research, engineering, and portfolio demonstration. It is not financial or trading advice and does not guarantee market outcomes.
