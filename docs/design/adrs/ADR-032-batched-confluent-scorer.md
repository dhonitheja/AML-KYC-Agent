---
id: "ADR-032"
title: "Batched confluent_kafka scorer with one DB transaction per poll"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-24"
author: "adr-author-agent"
supersedes: ["ADR-006"]
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-009"]
evidence: "benchmark"
---

# ADR-032: Batched confluent_kafka scorer with one DB transaction per poll

## Status
Accepted by the user at the Phase 6 design check (2026-11-24). Supersedes ADR-006 for the scorer; ingest already used confluent_kafka.

## Context
NFR-009 requires 1,000 scored/s. The Quix scorer committed one DB transaction per message and made about eight round trips per event, measured at about 130/s. Quix hides commit mechanics, so a batch transaction was not possible without fighting the framework.

## Decision
We will run the scorer as a plain confluent_kafka consumer (group `aml-scorer-v1`, manual commit), the same pattern as ingest and the investigator. Per poll (up to 500 messages, 20 ms timeout), one DB transaction runs:
- `record_transactions`: one `INSERT … SELECT … ON CONFLICT DO NOTHING` in id order, then a COPY of the `transaction.recorded` audit rows.
- `payment_screen_batch`: one screening insert, then a COPY of the audit rows.
- One prior-`scored.v1` lookup for the batch.
- One Redis pipeline of velocity scripts. Redis runs them in order, so per-account counts match one-at-a-time.
- One history prefetch for the batch's accounts, extended in memory as each event is scored.
- `rules.assess` per event, in partition order.
- A COPY of the `scored.v1`/`alerted.v1` rows.

Alerts are produced after the DB commit and offsets are committed after the producer flush, with delivery errors checked. Ingest uses the same write path, so both take transaction row locks in id order and cannot deadlock.

## Consequences
Positive: about 3 times fewer round trips per event, and Quix is removed (one Kafka client style, one fewer pinned supply-chain item). The 20 ms poll adds little to alert latency (p95 59 ms measured). Replay semantics are unchanged and covered by `tests/test_scoring_batch.py`. Negative: one bad message fails its whole batch, which is then retried from the last committed offset. Velocity entries from a failed batch stay in Redis. `ZADD NX` alone would dedupe members but let a retried event count later batch members with the same or earlier event time, so the script also stores each event's first counts (`velocity-counts:<account>`, pruned with the 48 h window) and returns them on retry (`test_failed_batch_retry_keeps_first_velocity_counts`). History is prefetched per batch, so rule cost still grows with an account's 48 h history.
