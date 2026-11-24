---
id: "CS-002"
title: "Scorer: Quix streaming scoring pipeline"
type: "component-spec"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["scoring.py"]
satisfies_fr: ["FR-002", "FR-003", "FR-004", "FR-007"]
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-004"]
constrained_by_adrs: ["ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006", "ADR-007", "ADR-008", "ADR-009", "ADR-013", "ADR-016"]
---

# CS-002: scoring.py

## Description
Quix Streams consumer (group `aml-scorer-v1`) on `transactions` that, per message and in ONE DB transaction, records the transaction, payment-screens it, scores it and writes `scored.v1` (+ `alerted.v1`). Alerts are published to `alerts` after the commit.

## Public Interface
- `run()` (scoring.py:25-54), process entrypoint `python -u scoring.py` (compose.yaml:47). Inner `score(row)` (scoring.py:30-50) returns the `scored.v1` inputs dict.
- `VELOCITY` Lua script (scoring.py:15-22).
- Output: topic `alerts`, value = `scored.v1` inputs `{transaction_id, case_id, run_id, version, score, alert, rules:[{rule, points, evidence}]}` (rules.py:30-31). Contains no account field.

## Internal Data Structures
- Redis sorted set `velocity:<account>`: score = event-time epoch seconds, member = transaction id.
- `history`: rows `{id, counterparty, amount_cents, direction, channel}` of already-scored transactions in the 48 h before `occurred_at` (scoring.py:40-43).

## Key Algorithms
1. `record_transaction` (CS-001, scoring.py:32).
2. `payment_screen` (CS-004, scoring.py:33).
3. Replay check: an existing `scored.v1` is returned unchanged, no new rows (scoring.py:34-37).
4. Lua: `ZADD NX` (retry counts once), trim to 48 h before latest, `EXPIRE 172800`, return ZCOUNT over (t-60,t] and (t-3600,t] (scoring.py:16-21).
5. History query (scoring.py:40-43), `rules.assess` (scoring.py:44).
6. Insert `scored.v1`, and `alerted.v1` when score >= 60 (scoring.py:45-49).
7. `filter(alert)` then `to_topic("alerts")` (scoring.py:53).

## Component Interactions
Kafka in/out via Quix (DI-003), Redis (DI-006), Postgres (DI-002), CS-003, CS-004. Quix publishes after DB commit, so duplicate alerts are possible (at-least-once); consumers (CS-008) must dedupe.

## Invariants
- One `scored.v1` and one `alerted.v1` per transaction (`audit_score_once`, sql/002-scoring.sql:4).
- Event time, not wall clock, drives windows.
- `autocommit=True` connection with an explicit `db.transaction()` per message.

## Traceability
FR-002, FR-003, FR-004, FR-007 (invocation); NFR-001 (p95 < 500 ms), NFR-002, NFR-004.
