---
id: "CS-006"
title: "Read API and onboarding endpoint"
type: "component-spec"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["api.py"]
satisfies_fr: ["FR-005", "FR-008"]
satisfies_nfr: ["NFR-002", "NFR-003", "NFR-004", "NFR-008"]
constrained_by_adrs: ["ADR-003", "ADR-009", "ADR-012", "ADR-013", "ADR-015", "ADR-016", "ADR-026", "ADR-028"]
---

# CS-006: api.py

## Description
FastAPI app (`uvicorn api:app`, published on 127.0.0.1:8000, compose.yaml:58-59) exposing read access to decisions and idempotent onboarding.

## Public Interface
- `GET /scores/{transaction_id}` (api.py:10-17): UUID path param; returns the `scored.v1` inputs or 404 "No recorded score".
- `GET /alerts` (api.py:20-24): latest 100 `alerted.v1` inputs by `event_id DESC`.
- `POST /onboarding` (api.py:32-49, body `Application`): runs `review`, inserts into `kyc_applications ON CONFLICT DO NOTHING`; an existing identical body returns the stored result, a different body raises 409 (api.py:41-44); otherwise audits `kyc.reviewed.v1` (without screening) plus one `onboarding.screened.v1` per subject.

## Internal Data Structures
Table `kyc_applications(id, application jsonb, result jsonb, created_at)`. Request/response models are `kyc.Application` and the `review` dict.

## Key Algorithms
Idempotency: `ON CONFLICT DO NOTHING RETURNING id`, then JSON equality of the stored `application` against the dumped body.

## Component Interactions
Connects per request as `aml_worker` (`pipeline.DSN`); uses CS-004, CS-005; DI-004, DI-005. No investigation endpoint in Phase 4 (FR-009.8); narratives are read from `audit`.

## Invariants
Read endpoints are SELECT-only; onboarding is idempotent by `application_id`; the API port binds to loopback only.

## Traceability
FR-008, FR-005; NFR-002, NFR-003, NFR-004.

## Deployment note (NFR-008, ARCH-001 B18, ADR-028)
`api` is attached to the `internal` network plus one non-internal `ingress` network, used only to publish `127.0.0.1:8000`. `api.py` makes no outbound network calls (NFR-008 AC-5 grep scope: no `urllib`, `requests`, `httpx`, `socket` or network SDK imports). The ingress network gives it a technical outbound route, recorded as residual risk RR-23; the control is the absence of outbound code. Postgres, Redis and Kafka are reached over `internal`.

## Change notes
- v1.1 (2026-11-23, NFR-008): NFR-008 added to `satisfies_nfr`; deployment note and RR-23 reference. No code-behavior change.
