---
id: "US-017"
title: "Auditor sees which model and prompt produced a narrative"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "auditor"
implements_fr: ["FR-009"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-017: Auditor sees which model and prompt produced a narrative

## Story
As an **auditor**, I want **each narrative recorded as an append-only audit event with model_version and prompt_version**, so that **I can reproduce and attribute AI-assisted output**.

## Acceptance Criteria
- [x] AC-1: Given a narrative is generated, when the investigation.drafted.v1 event is written, then model_version and prompt_version are populated and actor is investigator-v1.
- [x] AC-2: Given the audit table, when the agent writes, then only INSERT is used and no existing row is changed.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_drafted_row_stub) | model_version and prompt_version are populated and actor is investigat |
| AC-2 | tests/test_investigator.py (test_stack_update_delete_rejected, test_stack_role_privileges) | only INSERT is used and no existing row is changed |
