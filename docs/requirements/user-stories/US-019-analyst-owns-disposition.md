---
id: "US-019"
title: "Analyst, not the agent, makes the disposition"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-009"]
implements_nfr: ["NFR-005"]
test_files: ["tests/test_grounding.py", "tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-019: Analyst, not the agent, makes the disposition

## Story
As an **AML compliance analyst**, I want **the agent to only recommend**, so that **the disposition of an alert is always a human decision**.

## Acceptance Criteria
- [x] AC-1: Given a drafted narrative, when its recommendation is stored, then the value is advisory only: escalate_for_review or no_further_action_suggested.
- [x] AC-2: Given any recommendation, when it is stored, then no account is blocked, no alert closed and no case status changed by the agent.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_grounding.py (test_bad_recommendation_rejected) | the value is advisory only: escalate_for_review or no_further_action_s |
| AC-2 | tests/test_investigator.py (test_stack_scored_and_alerted_unchanged, test_stack_role_privileges) | no account is blocked, no alert closed and no case status changed by t |
