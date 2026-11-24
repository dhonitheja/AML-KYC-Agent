---
id: "FR-001"
title: "Replay-safe transaction ingestion"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["pipeline.py", "sql/001-foundations.sql", "sql/002-scoring.sql", "compose.yaml"]
test_files: ["tests/test_database.py", "tests/test_rules.py"]
depends_on: []
implements: []
---

# FR-001: Replay-safe transaction ingestion

## Description
Transactions arrive on the Kafka topic `transactions` and are persisted to Postgres with exactly one `transaction.recorded` audit entry each, even under redelivery. Also covers the synthetic seed/generate/benchmark CLI.

## Requirements

### FR-001.1: Single idempotent write path
`record_transaction()` SHALL insert into `transactions` with `ON CONFLICT(id) DO NOTHING` and SHALL write a `transaction.recorded` audit row (actor `ingest-v1`) only when a new row was inserted. (pipeline.py:50-59)

**Acceptance Criteria:**
- AC-1: Calling it twice with the same row yields 1 `transactions` row and 1 `transaction.recorded` audit row.
- AC-2: The audit `inputs` contain the full record plus origin (topic, partition, offset).

### FR-001.2: Offset commit after DB commit
The `ingest` consumer (group `aml-ingest-v1`, auto-commit off, `earliest`) SHALL process each batch (up to 100) in one DB transaction and SHALL commit Kafka offsets synchronously only after that transaction commits. A message error SHALL abort the batch without committing. (pipeline.py:62-83)

**Acceptance Criteria:**
- AC-1: Auto-commit is disabled in the consumer config.
- AC-2: A failure inside the batch transaction leaves offsets uncommitted so the batch is redelivered and no duplicate rows result.

### FR-001.3: One ingestion audit row per transaction (DB-enforced)
The schema SHALL enforce uniqueness of `transaction.recorded` per `transaction_id` via partial unique index `audit_ingestion_once`, while allowing multiple different audit actions per transaction. (sql/002-scoring.sql:3)

**Acceptance Criteria:**
- AC-1: A second `transaction.recorded` insert for the same transaction fails.
- AC-2: `scored.v1` and `transaction.recorded` rows may coexist for one transaction (tests/test_database.py::test_replay_is_idempotent_and_multiple_audit_actions_allowed).

### FR-001.4: Synthetic event generation
`event()` SHALL generate deterministic uuid5 transaction IDs per run; the `seed` command SHALL emit the AML-1042 scenario (two credits 4,820,000 + 3,560,000 cents, then a 8,090,000-cent debit, case `AML-1042`, account `DEMO-1042`); `generate` SHALL emit `--rate` x `--seconds` events (defaults 50, 60). Messages SHALL be keyed by account. Non-positive rate/seconds SHALL be rejected. (pipeline.py:16-47, 108-123)

**Acceptance Criteria:**
- AC-1: Same run UUID and index yield the same ID (tests/test_rules.py::test_unique_and_repeatable_ids).
- AC-2: Seed totals match $83,800 credits and $80,900 debit (tests/test_rules.py::test_seed_totals).
- AC-3: `--rate 0` or `--seconds 0` exits with an argparse error.

### FR-001.5: Ingestion throughput benchmark
`benchmark` SHALL offer 60 msg/s for `--seconds`, wait up to seconds+60 s, and pass only if persisted rows == audited rows == expected and persisted rate >= 50 rows/s; it SHALL print a JSON result and exit 0/1 accordingly. (pipeline.py:86-105)

**Acceptance Criteria:**
- AC-1: Exit code 1 if rows != audited or rate < 50.
- AC-2: Output JSON has `rows`, `audited`, `expected`, `persisted_per_second`, `passed`.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-001.1 | tests/test_database.py | pipeline.py:50-59 |
| FR-001.2 | none (gap); exercised end-to-end by CI benchmark (.github/workflows/ci.yml:14) | pipeline.py:62-83 |
| FR-001.3 | AC-1: none (gap); AC-2: tests/test_database.py | sql/002-scoring.sql:3 |
| FR-001.4 | tests/test_rules.py | pipeline.py:16-47,108-123 |
| FR-001.5 | CI benchmark step | pipeline.py:86-105 |
