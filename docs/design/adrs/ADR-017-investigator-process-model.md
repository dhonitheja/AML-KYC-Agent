---
id: "ADR-017"
title: "Investigator process model"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-005"]
evidence: "inferred"
---

# ADR-017: Investigator process model

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
FR-009 adds an agent that drafts a narrative for each alert using a model call that can take tens of seconds. The scorer path is latency-gated (NFR-001), alerts are published to a single-partition `alerts` topic (ADR-002), and exactly one advisory outcome per alert must be recorded (NFR-002). Existing patterns: commit-after-DB (ADR-005, pipeline.py:75-81) and replay check (scoring.py:34-37). Design decision D1, with D9 (publishes nothing, writes no cases, asynchronous).

## Decision
We will run the investigator as a separate compose service using a synchronous `confluent_kafka` consumer (group `aml-investigator-v1`, auto-commit off), one alert at a time, with these rules:
1. The model call happens OUTSIDE any DB transaction. Sequence: short transaction to take `pg_advisory_xact_lock(hashtext(alert_key))` and pre-check for an existing outcome; commit (lock released); model call; short transaction to INSERT the outcome with bare `ON CONFLICT DO NOTHING`; then commit the Kafka offset.
2. The advisory lock and pre-check only avoid duplicate model calls; integrity comes from the unique indexes (ADR-023).
3. At startup it asserts the `alerts` topic has exactly one partition (the single-consumer assumption) and fails fast otherwise.
4. `max.poll.interval.ms >= LLM_TIMEOUT_SECONDS x LLM_MAX_ATTEMPTS + backoff + 60 s` so a slow model call does not trigger a rebalance.
5. D9 (recommend-only extension of ADR-016): the investigator never publishes to Kafka, writes no `cases` rows, takes no action on transactions, runs asynchronously from the scorer (so it cannot add latency to the scoring path), and its output is an audit row labelled as a draft.

## Alternatives rejected
- Quix Streams (as in ADR-006): hides poll and commit timing, which we must size against a long blocking model call.
- Holding a DB transaction across the model call: would pin a connection and locks for tens of seconds and risk idle-in-transaction timeouts.

## Consequences
Positive: scorer latency and throughput are untouched; DB integrity does not depend on the lock; behavior on crash is a re-delivery that the pre-check or indexes absorb. Negative (cost accepted): the lock is transaction-scoped, so with a second consumer a duplicate model call (cost only, not a duplicate row) is possible (RR-14); a single consumer and single partition limit throughput; a long model call can delay later alerts; `max.poll.interval.ms` must be recomputed whenever timeout or attempts change. Serves NFR-001 (isolation), NFR-002, NFR-005 (D9).
