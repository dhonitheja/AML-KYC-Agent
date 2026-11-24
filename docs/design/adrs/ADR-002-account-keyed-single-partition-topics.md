---
id: "ADR-002"
title: "Account-keyed single-partition topics"
type: "adr"
status: "superseded"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: "ADR-033"
satisfies_nfr: ["NFR-001", "NFR-002"]
evidence: "documented"
---

# ADR-002: Account-keyed single-partition topics

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Velocity counters and the per-account history query (scoring.py:13 comment, scoring.py:15-22) assume updates for an account are processed serially. The producer keys by account (pipeline.py:44); compose creates `transactions` and `alerts` with `-p 1` (compose.yaml:14). R-02.

## Decision
We will key messages by account and run both topics with one partition, so ordering is total and one scorer instance serializes all updates.

## Consequences
Positive: no cross-worker race on velocity or history; simple replay reasoning (NFR-002). Negative: a hard throughput ceiling and no horizontal scaling of the scorer; the NFR-001 gates (50 rows/s, p95 < 500 ms in CI) are the evidence it is adequate. ADR-017 and ADR-023 rely on the `alerts` topic also being single-partition (asserted at investigator startup).
