---
id: "US-001"
title: "Replay-safe transaction ingestion"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-001"]
implements_nfr: ["NFR-002"]
test_files: ["tests/test_database.py"]
epic: "ingestion"
---

# US-001: Replay-safe transaction ingestion

## Story
As a **platform engineer**, I want **re-delivered Kafka transactions never create duplicate rows**, so that **a Kafka replay cannot double-count or double-audit a transaction**.

## Acceptance Criteria
- [ ] AC-1: Given a transaction already persisted, when the same message is consumed again, then no new row and no new transaction.recorded audit entry exist.
- [ ] AC-2: Given a newly inserted transaction, when it is recorded, then exactly one transaction.recorded audit row is written and the offset is committed only after the DB commit.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_database.py::test_replay_is_idempotent_and_multiple_audit_actions_allowed | no new row and no new transaction.recorded audit entry exist |
| AC-2 | none yet (gap) | exactly one transaction.recorded audit row is written and the offset is committed only after the DB commit |
