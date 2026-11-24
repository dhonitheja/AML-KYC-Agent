---
id: "DI-006"
title: "redis-py (Redis client; Redis server)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "redis"
version_constraint: ">=5,<7"
satisfies_fr: ["FR-003", "FR-002"]
satisfies_nfr: ["NFR-001", "NFR-002"]
constrained_by_adrs: ["ADR-007"]
---

# DI-006: redis

## Purpose
Event-time velocity windows for the scorer against `redis:7-alpine` with AOF (compose.yaml:30-33).

## Classes/Methods/Functions Used
`Redis(host="redis").register_script(VELOCITY)` and the returned script callable `velocity(keys=["velocity:<account>"], args=[epoch_seconds, transaction_id])` (scoring.py:28, 39). Lua uses `ZADD NX`, `ZREVRANGE ... WITHSCORES`, `ZREMRANGEBYSCORE`, `EXPIRE 172800`, `ZCOUNT` (scoring.py:16-21).

## Data Exchanged
Sorted sets keyed `velocity:<account>`: member = transaction id, score = event-time epoch seconds. Returns `[count_60s, count_3600s]`.

## Failure Modes and Timeouts
- No socket timeout is configured on the client; a hung Redis stalls the scorer.
- Redis is not the system of record: retries are safe because `NX` counts a transaction once; loss of Redis state under-counts velocity (rules still score, flagged as an accepted degradation).
- Script runs atomically server-side; the 48 h trim and expiry bound memory.

## Security Notes
Unauthenticated, no TLS, internal compose network only. Keys contain account ids (synthetic). Production: `requirepass`/ACLs, TLS, and a socket timeout. The investigator does not use Redis.

## Why This Dependency
Atomic sorted-set windows with Lua. Replacing it needs an equivalent atomic windowed counter (e.g. Postgres query over `transactions` with a latency penalty against the 500 ms gate).
