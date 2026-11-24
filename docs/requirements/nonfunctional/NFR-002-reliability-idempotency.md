---
id: "NFR-002"
title: "Replay-safe, idempotent processing"
type: "nonfunctional"
category: "reliability"
focus_track: "quality"
priority: "P0"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["pipeline.py", "scoring.py", "sql/002-scoring.sql", "api.py"]
test_files: ["tests/test_database.py", "tests/test_kyc.py"]
verification_method: "test"
---

# NFR-002: Replay-safe, idempotent processing

Focus track: quality (ISO/IEC 25010, reliability: recoverability, fault tolerance).

## Description
Processing must be replay-safe and idempotent: DB-enforced uniqueness, offsets committed after DB commit, and at-least-once alerts deduped by consumers.

## Requirements
- Writes SHALL be replay-safe: `record_transaction()` uses `INSERT ... ON CONFLICT DO NOTHING` and audits only newly inserted rows (`pipeline.py`).
- Uniqueness SHALL be DB-enforced by partial unique indexes: one ingestion row, and one `scored.v1` / `alerted.v1` row per transaction (`sql/002-scoring.sql:3-4`).
- Kafka offsets SHALL be committed only after the DB transaction commits (`pipeline.py:75-81`).
- Velocity windows SHALL count retries once via Redis `ZADD NX` (`scoring.py`); a replay reuses the prior `scored.v1` result.
- Alerts are at-least-once (published after DB commit); consumers SHALL dedupe by `transaction_id` + rule version.
- `POST /onboarding` is idempotent by `application_id`; same ID with a different payload returns 409 (`api.py`).
- (Phase 4, FR-009/FR-010, built) Every consumed alert SHALL end with exactly one drafted (`investigation.drafted.v1`) or skipped (`investigation.skipped.v1`) record, despite redelivery: at most one `investigation.drafted.v1` (unique on `transaction_id`) and at most one `investigation.skipped.v1` (unique on `inputs->>'alert_key'`) per alert, each enforced by a partial unique index in an idempotent migration; a partial unique index on `inputs->>'alert_key'` spanning both actions (drafted rows carry `alert_key` = `transaction_id`) makes the two mutually exclusive, and the pre-check before any model call avoids redundant calls.

## Verification Method
Automated tests in `tests/test_database.py` and `tests/test_kyc.py` (replay, uniqueness and `POST /onboarding` idempotency behaviour).

Related: FR-001, FR-002, FR-003, FR-004, FR-005, FR-009.

## Change Notes
- v1.1: Design amendment: combined `alert_key` unique index wording (one partial unique index on `inputs->>'alert_key'` spanning both drafted and skipped actions, making them mutually exclusive).
