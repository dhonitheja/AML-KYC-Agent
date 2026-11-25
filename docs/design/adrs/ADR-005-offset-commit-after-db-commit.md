---
id: "ADR-005"
title: "Kafka offset commit after DB commit"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-002"]
evidence: "partial"
---

# ADR-005: Kafka offset commit after DB commit

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Ingest consumes batches of 100, writes them in one DB transaction, then calls `consumer.commit(asynchronous=False)` with auto-commit off (pipeline.py:66-81). Since Phase 6 (ADR-032) the scorer is a confluent_kafka consumer with auto-commit off: per poll it runs one DB transaction, produces that batch's alerts, flushes the producer, checks delivery errors, and only then calls `consumer.commit(asynchronous=False)`. Before Phase 6 it relied on Quix checkpoint semantics, which this repo did not assert (evidence `partial`). R-05.

## Decision
We will commit offsets only after the corresponding database transaction commits, accepting at-least-once delivery and relying on ADR-004 for idempotency.

## Consequences
Positive: no message is lost after a crash between consume and persist. Negative: duplicates after a crash are reprocessed (cost is the idempotent no-op); a malformed message crash-loops the consumer (RR-7). The ordering has no direct test (requirements gap FR-001.2).
