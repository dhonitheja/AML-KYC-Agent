---
id: "FR-003"
title: "Event-time velocity counters"
type: "functional"
priority: "P1"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["scoring.py"]
test_files: ["tests/test_rules.py"]
depends_on: ["FR-002"]
implements: []
---

# FR-003: Event-time velocity counters

## Description
Per-account transaction counts over 1-minute and 1-hour windows, computed in Redis by one atomic Lua script keyed `velocity:<account>`. (scoring.py:15-22, 39)

## Requirements

### FR-003.1: Idempotent insertion
The script SHALL `ZADD NX` with score = event time (epoch seconds) and member = transaction id, so a retried event counts once. (scoring.py:16)

**Acceptance Criteria:**
- AC-1: Running the script twice for the same transaction id leaves counts unchanged.

### FR-003.2: Event-time windows
It SHALL return counts of members in `(t-60, t]` and `(t-3600, t]` where t is the event's `occurred_at`, not wall-clock time. (scoring.py:20-21, 38-39)

**Acceptance Criteria:**
- AC-1: An event exactly 60 s earlier is excluded from the minute count.
- AC-2: Replayed historical events produce counts based on their own timestamps.

### FR-003.3: 48-hour retention
It SHALL trim members older than latest-score minus 172800 s and set key `EXPIRE` 172800 s. (scoring.py:17-19)

**Acceptance Criteria:**
- AC-1: Members > 48h older than the newest are removed.
- AC-2: An idle key expires after 48h.

### FR-003.4: Feeds velocity rules
Counts SHALL be passed to `assess` as `minute_count`, `hour_count` (see FR-002.1 minute_velocity >= 10, hour_velocity >= 40). Redis SHALL run with append-only persistence. (compose.yaml:30-33)

**Acceptance Criteria:**
- AC-1: minute_count 10 triggers minute_velocity (tests/test_rules.py::test_remaining_rules, at-threshold only); 9 does not trigger: none (gap).

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-003.1-3 | none (needs Redis; gap) | scoring.py:15-22 |
| FR-003.4 | tests/test_rules.py | scoring.py:39; compose.yaml:30-33 |
