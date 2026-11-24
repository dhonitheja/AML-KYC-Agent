---
id: "ADR-014"
title: "Idempotent migrations re-run on every startup"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-002", "NFR-007"]
evidence: "documented"
---

# ADR-014: Idempotent migrations re-run on every startup

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
compose.yaml:24 mounts the whole `./sql` directory at `/docker-entrypoint-initdb.d`, so on a fresh volume 001, 002 and 003 all run at Postgres initdb; on an existing volume initdb does not run again. The `migrate` service re-runs 002 and 003 at every `compose up` as superuser with ON_ERROR_STOP (compose.yaml:34-39); they use `IF NOT EXISTS`/`DROP ... IF EXISTS` inside a transaction (sql/002-scoring.sql:1-6; sql/003-kyc.sql:1-11). R-14.

## Decision
We will write migrations 002 onward to be idempotent and re-run them on every start via a `migrate` one-shot, with no migration version table.

## Consequences
Positive: upgrading an existing volume needs no manual step. Negative: no ordering or version tracking; 001 is not re-applied to existing volumes (initdb runs only on a fresh volume); migrations run as superuser, so grants-only protection is bypassable (ADR-024); every future migration, including 004 for Phase 4, must stay idempotent.

## Phase 4 amendment (proposed, see ADR-018)
initdb will mount only `sql/001-foundations.sql` (not the whole `./sql` directory); `migrate` will run 002, 003 and 004. This keeps 004, which needs the investigator DB password secret (ADR-018, ADR-021), out of initdb, where no secret is available. The decision above (idempotent migrations re-run on every start) is unchanged; the amendment takes effect only if ADR-018 is accepted.
