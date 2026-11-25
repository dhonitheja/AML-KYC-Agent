---
id: "DI-005"
title: "uvicorn (ASGI server)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "uvicorn"
version_constraint: ">=0.30,<1"
satisfies_fr: ["FR-008", "FR-005"]
satisfies_nfr: ["NFR-007"]
constrained_by_adrs: ["ADR-012", "ADR-026"]
---

# DI-005: uvicorn

## Purpose
Runs `api:app` (compose.yaml:58: `uvicorn api:app --host 0.0.0.0 --port 8000`).

## Classes/Methods/Functions Used
CLI only; no import in source.

## Data Exchanged
HTTP/1.1 requests and responses for CS-006.

## Failure Modes and Timeouts
Process exit is not restarted (the `api` service has no `restart` policy, compose.yaml:53-61). Default keep-alive timeout applies; no explicit limits set.

## Security Notes
Binds 0.0.0.0 inside the container. From the host, exposure is limited by the mapping `127.0.0.1:8000:8000`. Every container on the `internal` network can also reach `api:8000` directly, and `GET /alerts`, `GET /scores/{transaction_id}` and `POST /onboarding` have no authentication, so the design trusts every service on that network; only the `/console` routes require analyst Basic auth (ADR-031). No TLS.

## Why This Dependency
Standard ASGI server for FastAPI; replaceable by hypercorn or gunicorn with uvicorn workers by changing only the compose entrypoint.
