---
id: "US-030"
title: "Record a human disposition for an alert"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-24"
author: "requirement-author-agent"
reviewer: ""
persona: "AML analyst"
implements_fr: ["FR-012"]
implements_nfr: ["NFR-005"]
test_files: ["tests/test_console.py"]
epic: "analyst-console"
---

# US-030: Record a human disposition for an alert

## Story
As an **AML analyst**, I want **to see each open alert with its evidence and the AI draft and record my decision with a rationale**, so that **every alert has an accountable human outcome in the audit trail**.

## Acceptance Criteria
- [x] AC-1: Given I sign in, when I open the console, then I see undecided alerts with rules, transaction and draft (FR-012.1, FR-012.2).
- [x] AC-2: Given an open alert, when I submit a disposition and rationale, then one audit row records it under my name and the alert leaves the queue (FR-012.3 AC-1).
- [x] AC-3: Given a colleague already decided an alert, when I submit, then I get a conflict and nothing is written (FR-012.3 AC-1).

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_console.py (test_console_requires_valid_credentials, test_decision_recorded_once_with_analyst_identity) | auth and queue contents |
| AC-2 | tests/test_console.py (test_decision_recorded_once_with_analyst_identity) | row, actor, queue removal |
| AC-3 | tests/test_console.py (test_decision_recorded_once_with_analyst_identity) | 409 for second analyst |
