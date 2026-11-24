---
id: "ADR-003"
title: "Postgres audit table as system of record, append-only via grants"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-004"]
evidence: "documented"
---

# ADR-003: Postgres audit table as system of record, append-only via grants

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Every decision (transaction recorded, scored, alerted, KYC, screening) must be reproducible from stored inputs (NFR-004). sql/001-foundations.sql:15-19 defines `audit` (event_id identity, recorded_at, actor, action, case_id, transaction_id, inputs jsonb, model_version, prompt_version). Lines 21-23 grant `aml_worker` only SELECT and INSERT (sql/003-kyc.sql:10 does the same for later tables), so the runtime role cannot UPDATE or DELETE audit rows. R-03.

## Decision
We will use the Postgres `audit` table as the system of record for all decisions and make it append-only for the runtime role by granting INSERT/SELECT only. Redis velocity state is derived; the DB is authoritative.

## Consequences
Positive: one queryable, transactional record, read via the API (api.py:13,23). Negative: grants alone do not stop the owner or a superuser, and `actor` is a self-asserted string because three services share one role (pipeline.py:10; RR-13). ADR-024 adds triggers; ADR-018 gives the investigator its own role. No test asserts the denials (NFR-003 gap in the requirements traceability matrix).
