---
id: "CS-001"
title: "Pipeline: ingest, produce, record_transaction"
type: "component-spec"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["pipeline.py", "latency.py"]
satisfies_fr: ["FR-001", "FR-004"]
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-004", "NFR-006", "NFR-007"]
constrained_by_adrs: ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006", "ADR-009", "ADR-013", "ADR-014", "ADR-015", "ADR-026"]
---

# CS-001: pipeline.py (and latency.py)

## Description
Shared constants, synthetic event generator, Kafka producer, the Phase 1 `ingest` consumer, the single transaction write path, and the CLI for the `ingest` service. `latency.py` is the p95 alert-latency gate client.

## Public Interface
- Constants `TOPIC="transactions"`, `BROKER="kafka:9092"`, `DSN="postgresql://aml_worker:synthetic-worker@postgres/aml"` (pipeline.py:8-10; hard-coded, not env; synthetic demo credential only).
- `event(run, i, now, seed=False) -> dict` (pipeline.py:16-26): deterministic `uuid5(run, str(i))` id; seed mode yields the AML-1042 scenario (case_id `AML-1042`, account `DEMO-1042`, `SEED` rows at pipeline.py:11-13, fixed event times at pipeline.py:23).
- `produce(run, rate, count, seed=False)` (pipeline.py:29-47): idempotent producer (`enable.idempotence`), keyed by account, `list_topics` before pacing, `flush(30)`; raises `RuntimeError` on incomplete delivery.
- `record_transaction(db, row, origin)` (pipeline.py:50-59): `INSERT ... ON CONFLICT(id) DO NOTHING RETURNING id`; only a newly inserted row gets one `transaction.recorded` audit row (actor `ingest-v1`, inputs `{record, **origin}`).
- `ingest()` (pipeline.py:62-83): group `aml-ingest-v1`, `earliest`, auto-commit off, `consume(100, 0.25)`; batch in one `db.transaction()`, then `consumer.commit(asynchronous=False)` (pipeline.py:81).
- `benchmark(seconds)` (pipeline.py:86-105): offers 60/s; passes if rows == audited == count and throughput >= 50/s.
- CLI `ingest|seed|benchmark|generate` (pipeline.py:108-123).
- `latency.py:11-33` `sample()` produces the 3 Northstar events and times producer-to-`alerts` delivery; `latency.py:45-48` exits 0 iff p95 < 500 ms over 40 samples.

## Internal Data Structures
Event dict: `id, run_id, case_id, account, counterparty, amount_cents, direction, channel, occurred_at` (ISO-8601). `origin` dict: `{topic, partition, offset}` (ingest) or `{topic, account_key}` (scorer).

## Key Algorithms
- Idempotency: row-level PK conflict plus audit-only-on-insert; replay creates neither a row nor an audit entry. Backed by partial unique index `audit_ingestion_once` (sql/002-scoring.sql:3).
- At-least-once: offset committed strictly after the DB transaction commits.
- Pacing: `time.sleep(max(0, start + i/rate - monotonic()))`.

## Component Interactions
Produces to Kafka `transactions`; consumes it; writes `transactions` and `audit` via psycopg as `aml_worker` (DI-001, DI-002). `record_transaction` is also called by CS-002.

## Invariants
- `record_transaction` is the only transaction write path.
- No UPDATE/DELETE issued (NFR-003).
- All services run from one image; the Dockerfile must run as non-root (`useradd --system --uid 10001 app`, `USER app`), so bind-mounted `watchlists/` must be world-readable (watchlist.py:114 sets 0644).
- Config is hard-coded; the new investigator (CS-008) MUST NOT reuse `DSN` or the `aml_worker` role.

## Traceability
FR-001 (replay-safe ingest), FR-004 (latency gate); NFR-001 (benchmark/latency gates), NFR-002, NFR-004, NFR-006 (synthetic data), NFR-007 (CI). Tests: tests/test_database.py; benchmark and latency commands in CI.
