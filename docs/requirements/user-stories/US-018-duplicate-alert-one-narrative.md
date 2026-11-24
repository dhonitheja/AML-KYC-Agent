---
id: "US-018"
title: "Duplicate alert yields at most one draft"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-009"]
implements_nfr: ["NFR-002"]
test_files: ["tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-018: Duplicate alert yields at most one draft

## Story
As a **platform engineer**, I want **at-least-once alert delivery to produce at most one investigation.drafted.v1 per alert transaction_id, with every consumed alert ending in exactly one drafted or skipped record**, so that **redelivery does not create duplicate or conflicting drafts**.

## Acceptance Criteria
- [x] AC-1: Given an alert for a transaction_id already drafted, when it is delivered again, then no second investigation.drafted.v1 event is created (dedupe key: transaction_id).
- [x] AC-2: Given two concurrent deliveries, when both are processed, then a partial unique index on investigation.drafted.v1 keyed on transaction_id leaves one row.
- [x] AC-3: Given any consumed alert, when processing completes, then it has exactly one drafted or skipped record.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_redelivery_dedupes) | no second investigation.drafted.v1 event is created |
| AC-2 | tests/test_investigator.py (test_stack_duplicate_insert_violates_index) | a unique index leaves one row |
| AC-3 | tests/test_investigator.py (test_stack_redelivery_dedupes, test_stack_forced_raise_skip_and_redelivery) | every consumed alert ends with exactly one drafted or skipped record |
