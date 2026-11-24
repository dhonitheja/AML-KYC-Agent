---
id: "ADR-013"
title: "Hard-coded configuration, SDN_FILE the only environment variable"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-006", "NFR-007"]
evidence: "documented"
---

# ADR-013: Hard-coded configuration, SDN_FILE the only environment variable

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
DSN, broker and topic are module constants (pipeline.py:8-10); api and scorer import them from the ingest module (api.py:5; scoring.py:10). Only `SDN_FILE` is read from the environment (watchlist.py:100; compose.yaml:46,57). Credentials are synthetic demo values (compose.yaml:21; pipeline.py:10). R-13.

## Decision
We will keep configuration as code constants with `SDN_FILE` as the only runtime switch, to keep the demo zero-setup.

## Consequences
Positive: `docker compose up` works with no secrets or env files (NFR-006, NFR-007). Negative: shared role and password for ingest, scorer and api (RR-13); `pipeline.py` doubles as a config module; any real deployment needs a new mechanism. ADR-021 introduces secret files for new Phase 4 credentials only and does not alter this decision for existing services.

## Amendment (accepted 2026-11-24, see ADR-030)
Phase 4 adds investigator-only env vars (`LLM_MODE`, `DATA_CLASSIFICATION`, `LOCAL_LLM_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ATTEMPTS`, plus the `*_FILE` secret paths, FR-010.3, ADR-021/022/030). The Phase 1-3 services keep this decision: hard-coded config with `SDN_FILE` as their only env var. The decision text above is unchanged.
