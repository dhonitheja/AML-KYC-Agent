---
id: "ADR-012"
title: "FastAPI on loopback, no authentication"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-006"]
evidence: "documented"
---

# ADR-012: FastAPI on loopback, no authentication

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
api.py exposes `GET /scores/{id}`, `GET /alerts`, `POST /onboarding` with no authN/Z. compose.yaml:59 publishes `127.0.0.1:8000:8000` only; the container binds 0.0.0.0 inside the network (compose.yaml:58). Data is synthetic (ADR-015). R-12.

## Decision
We will serve the API with FastAPI/uvicorn, published to loopback only, with no authentication or access logging, relying on host-local access and pydantic validation (kyc.py:9-36).

## Consequences
Positive: minimal surface for a demo. Negative: not deployable beyond localhost; responses return raw audit `inputs` (api.py:17,24); no access log (RR-3, ASVS V2/V4/V7); one DB connection per request (api.py:12). Real use requires a new ADR adding authN/Z.
