---
id: "ADR-008"
title: "Pure rules engine"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-004"]
evidence: "documented"
---

# ADR-008: Pure rules engine

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
`rules.assess(row, minute_count, hour_count, history)` (rules.py:2-31) imports nothing and returns `{score, alert, rules[]}` with evidence ids per hit; alert threshold is score >= 60 (rules.py:29-31). The docstring marks the rules illustrative (rules.py:1). R-08.

## Decision
We will keep rule evaluation a pure function: all I/O (Redis counts, DB history) is gathered by the caller and passed in.

## Consequences
Positive: unit-testable without services (tests/test_rules.py), deterministic and reproducible from stored inputs (NFR-004), cheap on the latency path (NFR-001). Negative: callers must pre-fetch history, so the scorer owns query cost; thresholds are hard-coded and uncalibrated.
