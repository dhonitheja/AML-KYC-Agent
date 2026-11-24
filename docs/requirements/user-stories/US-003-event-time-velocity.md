---
id: "US-003"
title: "Event-time velocity counters"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-003"]
implements_nfr: ["NFR-002"]
test_files: ["tests/test_rules.py"]
epic: "detection"
---

# US-003: Event-time velocity counters

## Story
As an **AML compliance analyst**, I want **1-minute and 1-hour counts based on event time**, so that **bursts are detected correctly even when messages arrive late or are retried**.

## Acceptance Criteria
- [ ] AC-1: Given a transaction retried after a failure, when the velocity script runs again, then the event counts once (ZADD NX).
- [ ] AC-2: Given events older than 48 hours, when retention is applied, then they are no longer counted.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | none yet (planned) | the event counts once (ZADD NX) |
| AC-2 | none yet (planned) | they are no longer counted |
