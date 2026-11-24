---
id: "NFR-006"
title: "Synthetic data only; no credentials by default"
type: "nonfunctional"
category: "privacy"
focus_track: "security"
priority: "P0"
status: "approved"
version: "1.2"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["README.md", "CLAUDE.md", "compose.yaml", "pipeline.py"]
test_files: ["tests/test_rules.py", "tests/test_kyc.py"]
verification_method: "test"
---

# NFR-006: Synthetic data only; no credentials by default

Focus track: security (ISO/IEC 27001, privacy). Also AI governance for Phase 4.

## Description
Only synthetic data is used and no model credentials or real customer data are needed by default.

## Requirements
- In this repository, CI and the demo deployment, only synthetic data SHALL be used; Compose credentials are local demo values (CLAUDE.md; `README.md:19`). No model credentials or real customer data are needed by default.
- (Phase 4, FR-009/FR-010, built) The model switch SHALL be `LLM_MODE` (`stub` default | `local` | `anthropic`); `anthropic` is permitted only with `DATA_CLASSIFICATION=synthetic` (FR-010.6, NFR-008); CI and tests SHALL use `stub`; tests SHALL guard against real model calls (e.g. fail if a network model client is constructed).
- (Phase 4, FR-009/FR-010, built) When `LLM_MODE=anthropic`, only the minimal evidence needed for the narrative SHALL be sent; the API key is required only when `LLM_MODE=anthropic`. It SHALL be supplied by a secret file (`ANTHROPIC_API_KEY_FILE`), with the `ANTHROPIC_API_KEY` env var only as a local-development fallback, and SHALL never be committed, logged or audited. Only synthetic demo secrets under `secrets/demo/` may be committed. (Amended 2026-11-22 at Design, ADR-021.)
- The optional real OFAC list is public data and opt-in via `SDN_FILE`.

## Verification Method
Tests in `tests/test_rules.py` and `tests/test_kyc.py` use synthetic data only; code review of `README.md`, `CLAUDE.md` and `compose.yaml` for demo-only credentials.

Related: FR-009, FR-010, NFR-008.

## Change Notes
- v1.2 (2026-11-23, NFR-008 delta): `local` mode added; `anthropic` gated on `DATA_CLASSIFICATION=synthetic`. Data-boundary rules live in NFR-008. Scope narrowed to repo/CI/demo, since NFR-008 covers deployments that hold customer data.
- v1.1: Design amendment (2026-11-22, ADR-021): secret files (`ANTHROPIC_API_KEY_FILE`, env var only as local-dev fallback); only synthetic secrets may be committed under `secrets/demo/`.
