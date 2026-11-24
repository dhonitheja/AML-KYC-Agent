---
id: "DI-004"
title: "FastAPI (HTTP API framework)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "fastapi"
version_constraint: ">=0.115,<1"
satisfies_fr: ["FR-005", "FR-008"]
satisfies_nfr: ["NFR-003", "NFR-006"]
constrained_by_adrs: ["ADR-012"]
---

# DI-004: fastapi

## Purpose
Request validation and routing for the read API and onboarding (api.py).

## Classes/Methods/Functions Used
`FastAPI(title=...)` (api.py:7); `@app.get("/scores/{transaction_id}")` with `UUID` path type (api.py:10-11); `@app.get("/alerts")` (api.py:20-21); `@app.post("/onboarding")` with the pydantic `Application` body (api.py:32-33); `HTTPException(404|409)` (api.py:16, 44).

## Data Exchanged
JSON: scored inputs, alert lists, onboarding application (identity data, synthetic only) and review result.

## Failure Modes and Timeouts
Invalid body or UUID returns 422 automatically; unknown score 404; conflicting application 409. No request timeout or rate limit is configured. Request bodies are bounded only by the field constraints in kyc.py (256-char strings, list maxima).

## Security Notes
No authentication or TLS: acceptable only because compose publishes it on `127.0.0.1:8000` (compose.yaml:59) with synthetic data. Production needs authN/Z and TLS termination. No investigation endpoint is added in Phase 4 (FR-009.8).

## Why This Dependency
Gives schema validation from pydantic models directly. Replacing with Flask/Starlette requires hand validation of `Application` and UUID parsing and reproducing 422/409 semantics.
