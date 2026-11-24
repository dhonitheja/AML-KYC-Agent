---
id: "ADR-007"
title: "Redis Lua event-time velocity windows"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-002"]
evidence: "documented"
---

# ADR-007: Redis Lua event-time velocity windows

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Rules need 60 s and 1 h transaction counts per account on event time, with retries counted once (FR-003). scoring.py:15-22 registers a Lua script: `ZADD NX` (score = event time, member = transaction id), trim to 48 h behind the latest score, `EXPIRE 172800`, return two `ZCOUNT` values. Redis runs with AOF (compose.yaml:32). R-07.

## Decision
We will keep velocity windows in a Redis sorted set updated atomically by a Lua script, keyed by account and scored by event time.

## Consequences
Positive: O(log n) updates, atomic, retry-safe via NX, correct for out-of-order arrival on event time. Negative: derived state outside the DB (rebuildable from `transactions`, not automated); Redis has no password or TLS (RR-1, B7); the script has no automated test (requirements gap FR-003).
