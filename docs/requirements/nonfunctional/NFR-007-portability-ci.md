---
id: "NFR-007"
title: "Docker Compose portability and CI budget"
type: "nonfunctional"
category: "compatibility"
focus_track: "quality"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["compose.yaml", "Dockerfile", ".github/workflows/ci.yml", "CLAUDE.md"]
test_files: ["tests/test_database.py"]
verification_method: "ci-matrix"
---

# NFR-007: Docker Compose portability and CI budget

Focus track: quality (ISO/IEC 25010, compatibility/portability).

## Description
The full stack runs via Docker Compose on Windows Docker Desktop and `ubuntu-latest` CI, within a 15-minute CI budget.

## Requirements
- The full stack SHALL run via Docker Compose on Windows Docker Desktop (Linux containers) and on `ubuntu-latest` CI.
- The CI job SHALL finish within 15 minutes (`ci.yml:5-6`): pytest, seed, `latency.py`, `/alerts` contains `AML-1042`, then benchmark.
- Code is baked in with `COPY *.py`; there is no source mount, so images MUST be rebuilt after edits (`docker compose up --build -d`).
- New services, topics (one-shot `topic` service) and migrations SHALL be wired in `compose.yaml`; migrations 002+ re-run every startup and MUST be idempotent.
- (Phase 4, FR-009/FR-010, built) Phase 4 SHALL add a CI step asserting a narrative exists for AML-1042.
- Known gap: CI `up -d` does not wait for readiness.

## Verification Method
CI on `ubuntu-latest` (`.github/workflows/ci.yml`) runs the stack end to end; `tests/test_database.py` runs in that job.

Related: FR-001, FR-008.
