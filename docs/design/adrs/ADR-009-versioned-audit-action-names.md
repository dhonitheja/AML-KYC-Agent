---
id: "ADR-009"
title: "Versioned audit action names"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004"]
evidence: "documented"
---

# ADR-009: Versioned audit action names

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Decision rows use suffixed action names: `scored.v1`, `alerted.v1` (scoring.py:45), `payment.screened.v1` (kyc.py:90), `kyc.reviewed.v1`, `onboarding.screened.v1` (api.py:46,48). Rule results also carry `version: "v1"` (rules.py:31). `transaction.recorded` (pipeline.py:59, sql/002-scoring.sql:3) is unversioned; this ADR records the convention for decision actions and flags that exception. R-09.

## Decision
We will version decision-bearing audit action names (`<noun>.<verb>.vN`) so a logic change can be distinguished in history and old rows remain interpretable.

## Consequences
Positive: reproducible history across rule changes (NFR-004). Negative: unique indexes and API queries match literal strings (sql/002-scoring.sql:4; api.py:13,23), so a version bump requires coordinated index, query and reader changes; the unversioned `transaction.recorded` is an inconsistency. Phase 4 actions (ADR-017) follow the convention.
