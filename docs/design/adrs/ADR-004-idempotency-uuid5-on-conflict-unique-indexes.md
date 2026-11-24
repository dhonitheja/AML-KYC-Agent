---
id: "ADR-004"
title: "Idempotency via uuid5 ids, ON CONFLICT and partial unique indexes"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-002"]
evidence: "documented"
---

# ADR-004: Idempotency via uuid5 ids, ON CONFLICT and partial unique indexes

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Kafka delivery is at-least-once (ADR-005), so replays and double deliveries must not duplicate rows. Event ids are deterministic `uuid5(run, i)` (pipeline.py:24). `record_transaction` uses `ON CONFLICT(id) DO NOTHING RETURNING id` and writes the audit row only when the insert happened (pipeline.py:54-59). sql/002-scoring.sql:3-4 drops the old single unique constraint and adds partial unique indexes `audit_ingestion_once` (action `transaction.recorded`) and `audit_score_once` (`scored.v1`, `alerted.v1`). The scorer also reuses an existing `scored.v1` row (scoring.py:34-37). R-04.

## Decision
We will enforce exactly-once effects through deterministic ids, `INSERT ... ON CONFLICT DO NOTHING`, and database partial unique indexes rather than application locking.

## Consequences
Positive: replay safety lives in the DB and survives crashes (NFR-002); tests/test_database.py exercises replay. Negative: every new action type needs its own index or it is not deduplicated (relevant to ADR-023); the Redis side relies on `ZADD NX` for the same property (ADR-007).
