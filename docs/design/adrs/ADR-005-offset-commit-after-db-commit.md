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
Ingest consumes batches of 100, writes them in one DB transaction, then calls `consumer.commit(asynchronous=False)` with auto-commit off (pipeline.py:66-81). The scorer uses Quix Streams (scoring.py:26-29), which manages its own commits; per Quix checkpoint semantics the offset is committed after the apply callback returns, i.e. after the per-message DB transaction (scoring.py:31) completes, but this is Quix behavior not asserted in this repo, hence evidence `partial`. R-05.

## Decision
We will commit offsets only after the corresponding database transaction commits, accepting at-least-once delivery and relying on ADR-004 for idempotency.

## Consequences
Positive: no message is lost after a crash between consume and persist. Negative: duplicates after a crash are reprocessed (cost is the idempotent no-op); a malformed message crash-loops the consumer (RR-7). The ordering has no direct test (requirements gap FR-001.2).
