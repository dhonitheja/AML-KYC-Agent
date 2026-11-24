---
id: "CS-007"
title: "SQL migrations 001-003 (schema and grants)"
type: "component-spec"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["sql/001-foundations.sql", "sql/002-scoring.sql", "sql/003-kyc.sql", "compose.yaml"]
satisfies_fr: ["FR-001", "FR-002", "FR-004", "FR-005", "FR-007"]
satisfies_nfr: ["NFR-002", "NFR-003", "NFR-004"]
constrained_by_adrs: ["ADR-003", "ADR-004", "ADR-009", "ADR-014", "ADR-024"]
---

# CS-007: sql/001..003

## Description
Schema, role and idempotency indexes. Current behavior: compose.yaml:24 mounts the whole `./sql` directory into `/docker-entrypoint-initdb.d`, so on a fresh volume initdb runs 001, 002 and 003 (and would run 004), and `migrate` then re-runs 002 and 003. Change (see CS-010): mount only `./sql/001-foundations.sql:/docker-entrypoint-initdb.d/001-foundations.sql:ro`, so initdb runs 001 only; `migrate` runs 002, 003 and 004 on every start, fresh volume included. `002` and `003` are re-run by the `migrate` service on every startup (compose.yaml:39) and must therefore be idempotent.

## Public Interface (DDL)
- 001-foundations.sql: `vector` extension (line 1, unused); role `aml_worker` (line 2); `cases` seeded with AML-1042 (lines 3-7); `transactions` with CHECKs on amount and direction (lines 8-13) and run_id index (line 14); `audit` (event_id identity, recorded_at, actor, action, case_id FK, transaction_id FK, inputs jsonb, model_version, prompt_version, lines 15-19); grants SELECT on cases/transactions/audit, INSERT on transactions/audit, USAGE on `audit_event_id_seq` (lines 21-23).
- 002-scoring.sql: `audit_ingestion_once` (transaction_id WHERE action='transaction.recorded', line 3), `audit_score_once` (transaction_id, action WHERE action IN scored/alerted, line 4), index `account_event_history(account, occurred_at)` (line 5); wrapped in BEGIN/COMMIT.
- 003-kyc.sql: `kyc_applications`, `screened_counterparties` (PK account, name_key, snapshot); `GRANT SELECT,INSERT ... TO aml_worker`.

## Internal Data Structures
Tables: `cases`, `transactions`, `audit`, `kyc_applications`, `screened_counterparties`.

## Key Algorithms
Idempotency by partial unique indexes plus `ON CONFLICT DO NOTHING` in callers.

## Component Interactions
CS-001/002/004/006 depend on these tables; CS-010 extends them.

## Invariants
- `aml_worker` has no UPDATE/DELETE and no INSERT on `cases`.
- New migrations MUST use IF NOT EXISTS and be appended to the migrate command.

## Traceability
FR-001, FR-002, FR-004, FR-005, FR-007; NFR-002, NFR-003 (least privilege), NFR-004.
