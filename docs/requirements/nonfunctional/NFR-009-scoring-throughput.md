---
id: "NFR-009"
title: "Scoring throughput of 1,000 transactions per second"
type: "nonfunctional"
category: "performance"
focus_track: "quality"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-24"
author: "requirement-author-agent"
reviewer: ""
source_files: ["scoring.py", "pipeline.py", "kyc.py", "compose.yaml", ".github/workflows/ci.yml"]
test_files: ["tests/test_scoring_batch.py", "tests/test_database.py"]
verification_method: "benchmark"
---

# NFR-009: Scoring throughput of 1,000 transactions per second

Focus track: quality (ISO/IEC 25010, performance efficiency). Phase 6. Extends NFR-001, which keeps its 50/s ingestion and p95 < 500 ms latency gates.

## Description
The scoring path SHALL sustain at least 1,000 transactions/s end to end, from producer to durable `scored.v1` rows, with every transaction also recorded and audited. The NFR-001 and NFR-002 guarantees still hold: alert latency p95 under 500 ms, exactly one decision per transaction, and replays reuse stored decisions.

## Requirements
- `pipeline.py loadtest --rate 1200 --seconds 60 --accounts 10000 --target 1000` offers 1,200/s over 10,000 accounts. It passes only if recorded == scored == expected and scored rows / elapsed (including drain) >= 1,000/s. Load-test accounts are scoped to the run, so each run starts with empty 48 h histories.
- The measurement is defined on fresh volumes (as CI provides). The investigator is stopped during the full gate because it is a separate asynchronous consumer (NFR-001).
- Batched scoring SHALL give the same score, alert and rule set as one-at-a-time scoring, including in-batch duplicates and replays (`tests/test_scoring_batch.py`).

## Verification Method
- Per push: `loadtest --rate 300 --seconds 20 --target 250` smoke step in the `benchmark` job (a 4-vCPU runner).
- Manual: the `load-test` workflow_dispatch job runs the full gate. Its `load_runner` input selects a larger runner, because a standard 4-vCPU runner is expected to fall short.
- Measured locally on 2026-11-24 (16-thread host, Docker Desktop, fresh volumes): 1,183, 1,192 and 1,191 scored/s at 1,200 offered; at least 1,585/s at 1,600 offered (kept up). Latency p95 59 ms.

## Known limits
- History-heavy accounts are slower: 100 accounts at 1,200/s gave 698/s, because every event loads that account's full 48 h history.
- Throughput falls as the database outgrows the Postgres cache. Locally a 2.8 GB, 4.3M-row database dropped it to about 600/s. Sustained operation needs audit retention or partitioning (ADR-025).
- The investigator processes alerts one at a time and falls behind under alert storms. That does not slow the scorer, but drafts arrive late.

Related: NFR-001, NFR-002, ADR-032, ADR-033.
