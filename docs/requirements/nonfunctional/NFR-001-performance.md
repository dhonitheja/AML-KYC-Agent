---
id: "NFR-001"
title: "Ingestion throughput and alert latency"
type: "nonfunctional"
category: "performance"
focus_track: "quality"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["pipeline.py", "latency.py", ".github/workflows/ci.yml"]
test_files: ["latency.py"]
verification_method: "benchmark"
---

# NFR-001: Ingestion throughput and alert latency

Focus track: quality (ISO/IEC 25010, performance efficiency).

## Description
Ingestion must sustain at least 50 transactions/s with full audit rows, and alert latency must stay under a p95 of 500 ms.

## Requirements
- The system SHALL persist at least 50 transactions/s with a matching `transaction.recorded` audit row per transaction. The benchmark offers 60/s for N seconds and passes only if rows == audit rows == expected count and throughput >= 50/s (`pipeline.py:89,102`); it gives up after `seconds + 60` s (`pipeline.py:98`).
- Alert latency SHALL be p95 < 500 ms over 40 samples (`latency.py:45-48`).
- (Phase 4, FR-009/FR-010, built) The Phase 4 investigation agent MUST NOT regress either gate. It SHALL run as a separate asynchronous consumer of the `alerts` topic, never inside the scorer DB transaction (CLAUDE.md Architecture, `scoring.py`).
- The 1,000 tx/s scoring target is NFR-009 (Phase 6).

## Verification Method
Benchmarks are CLIs (`pipeline.py benchmark`, `latency.py`), not test files; `latency.py` is listed in test_files as the latency gate.
`docker compose run --rm ingest benchmark --seconds 60` and `docker compose run --rm --entrypoint python ingest latency.py`; both run in CI.

Related: FR-001, FR-002, FR-004, FR-009.
