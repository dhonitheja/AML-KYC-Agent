---
id: "CS-002"
title: "Scorer: batched confluent_kafka scoring pipeline"
type: "component-spec"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["scoring.py"]
satisfies_fr: ["FR-002", "FR-003", "FR-004", "FR-007"]
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-004"]
constrained_by_adrs: ["ADR-003", "ADR-004", "ADR-005", "ADR-007", "ADR-008", "ADR-009", "ADR-013", "ADR-016", "ADR-032", "ADR-033"]
---

# CS-002: scoring.py

v1.1 (Phase 6): batched confluent_kafka scorer (ADR-032) over a 16-partition topic (ADR-033). Replaces the Quix design.

## Description
`SCORER_REPLICAS` (default 8) confluent_kafka consumers (group `aml-scorer-v1`, manual commit) on `transactions`. Per poll (up to 500 messages, 20 ms), ONE DB transaction records the transactions, payment-screens them, scores them and writes `scored.v1` (+ `alerted.v1`). Alerts are produced after the commit; offsets are committed after the producer flush.

## Public Interface
- `run()`, process entrypoint `python -u scoring.py`.
- `score_batch(db, velocity_script, redis, rows, origins=None)`: scores rows in order inside the caller's transaction and returns one `scored.v1` inputs dict per row. `origins` carries each message's topic, partition and offset into `transaction.recorded`.
- `VELOCITY` Lua script; `in_window(history, at)`.
- Output: topic `alerts`, value = `scored.v1` inputs `{transaction_id, case_id, run_id, version, score, alert, rules:[{rule, points, evidence}]}`, alerts only (score >= 60). Contains no account field.

## Internal Data Structures
- Redis `velocity:<account>` sorted set (event-time epoch, transaction id), trimmed to 48 h before the latest event.
- Redis `velocity-counts:<account>` hash (id -> first "minute,hour" counts): returned on a retry, never pruned by event time, deleted by `forget_counts(redis, rows)` after the batch's DB commit (key idle expiry 48 h).
- `history`: already-scored rows in the batch's 48 h range, prefetched once and extended in memory per event.

## Key Algorithms
1. `record_transactions` (CS-001), then `payment_screen_batch` (CS-004).
2. One prior-`scored.v1` lookup; replays and in-batch duplicates reuse the stored decision.
3. One Redis pipeline of `VELOCITY` for fresh events: stored counts if present, else `ZADD NX`, trim, ZCOUNT over (t-60,t] and (t-3600,t], store the counts.
4. One history prefetch, then `rules.assess` per event in partition order.
5. COPY `scored.v1`, and `alerted.v1` when score >= 60.
6. After the DB commit: `forget_counts`, produce alerts, flush, check delivery errors, commit offsets.

## Component Interactions
Kafka via confluent_kafka (DI-001), Redis (DI-006), Postgres (DI-002), CS-003, CS-004. Alerts are published after the DB commit, so duplicates are possible (at-least-once); consumers (CS-008) must dedupe.

## Invariants
- One `scored.v1` and one `alerted.v1` per transaction (`audit_score_once`, sql/002-scoring.sql).
- Event time, not wall clock, drives windows.
- Batched scoring gives the same results as one-at-a-time scoring (`tests/test_scoring_batch.py`).
