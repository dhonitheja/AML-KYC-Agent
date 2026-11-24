---
id: "NFR-004"
title: "Versioned, reproducible decision audit trail"
type: "nonfunctional"
category: "quality"
focus_track: "quality"
priority: "P0"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["sql/001-foundations.sql", "scoring.py", "kyc.py", "watchlist.py", "api.py"]
test_files: ["tests/test_database.py", "tests/test_kyc.py"]
verification_method: "test"
---

# NFR-004: Versioned, reproducible decision audit trail

Focus track: quality (ISO/IEC 25010, maintainability: analysability). Also supports ISO/IEC 27001 accountability.

## Description
Every decision is stored as a versioned `audit` row with its evidence, so decisions are reproducible and analysable.

## Requirements
- Every decision SHALL be an `audit` row with a versioned `action` (`scored.v1`, `alerted.v1`, `kyc.reviewed.v1`, `onboarding.screened.v1`, `payment.screened.v1`) and `inputs` jsonb holding the evidence (`sql/001-foundations.sql:15-19`).
- Screening decisions SHALL record the watchlist snapshot SHA-256 (`watchlist.py`); payment screening is keyed by (account, normalized name, snapshot).
- (Phase 4, FR-009/FR-010/FR-011, built) Phase 4 SHALL populate the existing `model_version` and `prompt_version` columns and record the gathered evidence in `inputs`. Drafted rows SHALL also record the grounding results and the `ai_generated` / `requires_human_review` labels (FR-011).
- `/scores/{id}` and `/alerts` read from `audit` (`api.py`).

## Verification Method
Automated tests in `tests/test_database.py` (multiple audit actions coexist per transaction) and `tests/test_kyc.py` (versioned `audit` rows). Gap: no test asserts evidence content in `inputs` (`test_database.py` inserts `{}`).

Related: FR-002, FR-004, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011.

## Change Notes
- v1.1: Phase 4 (proposed) clause extended with FR-011: drafted rows record grounding results and `ai_generated` / `requires_human_review` labels; FR-011 added to Related.
