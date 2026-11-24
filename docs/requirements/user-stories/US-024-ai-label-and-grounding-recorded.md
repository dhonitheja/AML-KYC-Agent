---
id: "US-024"
title: "Auditor sees the AI-generated label and grounding checks"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "auditor"
implements_fr: ["FR-011"]
implements_nfr: ["NFR-004", "NFR-005"]
test_files: ["tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-024: Auditor sees the AI-generated label and grounding checks

## Story
As an **auditor**, I want **every drafted row labeled as AI-generated with its grounding checks recorded**, so that **I can tell machine output from human decisions and see how it was verified**.

## Acceptance Criteria
- [x] AC-1: Given a drafted row is written, when I read it, then it carries ai_generated true, requires_human_review true and a grounding label.
- [x] AC-2: Given the grounding checks ran, when I read the drafted row, then the checks performed and their outcomes are recorded in the same audit row.
- [x] AC-3: Given any drafted row, when it is listed, then no row lacks the three labels.
- [x] AC-4: Given the audit table, when labels are written, then only INSERT is used and no existing row is changed.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_build_drafted_row_labels, test_stack_drafted_row_stub) | ai_generated, requires_human_review, grounding present |
| AC-2 | tests/test_investigator.py (test_build_drafted_row_labels) | grounding check outcomes stored in the row |
| AC-3 | tests/test_investigator.py (test_build_drafted_row_labels, test_stack_drafted_row_stub) | every drafted row is labeled |
| AC-4 | tests/test_investigator.py (test_stack_update_delete_rejected, test_stack_role_privileges) | append-only, INSERT only |
