---
id: "DI-002"
title: "psycopg 3 (PostgreSQL client; PostgreSQL server)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "psycopg[binary]"
version_constraint: "==3.2.6"
satisfies_fr: ["FR-001", "FR-002", "FR-005", "FR-007", "FR-008", "FR-009"]
satisfies_nfr: ["NFR-002", "NFR-003", "NFR-004", "NFR-006"]
constrained_by_adrs: ["ADR-003", "ADR-004", "ADR-013", "ADR-018"]
---

# DI-002: psycopg

## Purpose
PostgreSQL access to image `pgvector/pgvector:pg16` (compose.yaml:18), database `aml`; the audit system of record.

## Classes/Methods/Functions Used
- `psycopg.connect(DSN, autocommit=True[, row_factory=dict_row])` (pipeline.py:70, scoring.py:29), per-request `psycopg.connect(DSN)` (api.py:12).
- `db.transaction()` for atomic multi-statement units (pipeline.py:75, scoring.py:31); `db.execute(sql, params).fetchone()/fetchall()`.
- `psycopg.types.json.Jsonb` for jsonb parameters (kyc.py:6, pipeline.py:51).
- New (CS-008): two short transactions per alert; `pg_advisory_xact_lock(hashtext(%s))`; `SET LOCAL lock_timeout/statement_timeout`; `INSERT ... ON CONFLICT DO NOTHING`; startup `SELECT current_user`.
- Parameter binding is always used; no string-formatted SQL with data.

## Data Exchanged
Rows of `transactions`, `audit` (jsonb `inputs`), `kyc_applications`, `screened_counterparties`; investigator adds `investigation.drafted.v1`/`skipped.v1` rows with minimized evidence (CS-008).

## Failure Modes and Timeouts
- `UniqueViolation` or `ON CONFLICT` indicates replay; handled as no-op.
- Connection loss or lock timeout raises; the message offset is not committed, service restarts, redelivery is idempotent.
- No connect timeout is set today (`connect_timeout` should be added to the investigator connection).
- FK `audit.transaction_id -> transactions` fails for unknown ids, hence NULL transaction_id on skipped rows (FR-009.7).

## Security Notes
Roles: `aml_worker` (SELECT/INSERT only), new `aml_investigator` (CS-010: SELECT on `transactions` and view `investigator_audit` only, INSERT on `audit`; no `RETURNING` on its inserts). Demo DSN has a hard-coded synthetic password (pipeline.py:10); the investigator builds its connection from `INVESTIGATOR_DB_HOST` (default `postgres`), user `aml_investigator`, db `aml` and the password read from `INVESTIGATOR_DB_PASSWORD_FILE` (default `/run/secrets/investigator_db_password`, compose secret `investigator_db_password`, source `${INVESTIGATOR_DB_PASSWORD_SECRET:-./secrets/demo/investigator_db_password}`, synthetic committed demo value) with no fallback (`INVESTIGATOR_DSN`/`INVESTIGATOR_DSN_FILE` removed), never logs the password or DSN, and should use `sslmode=verify-full` outside Compose. `==` exact pin; `[binary]` ships libpq.

## Why This Dependency
Native jsonb adaptation, `transaction()` context manager, server-side binding. Replacing with psycopg2/asyncpg means rewriting every call site and the `Jsonb` wrapping; DB-side idempotency (indexes) is independent of the driver.
