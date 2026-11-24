---
id: "US-023"
title: "Narrative facts match the evidence"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-011"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_grounding.py", "tests/test_investigator.py", "tests/test_llm.py"]
epic: "investigation-agent"
---

# US-023: Narrative facts match the evidence

## Story
As an **AML compliance analyst**, I want **every fact in a drafted narrative checked against the evidence before it is stored**, so that **I never act on an invented amount, counterparty, rule or sanctions claim**.

## Acceptance Criteria
- [x] AC-1: Given a draft made of claim-level findings, when it is checked, then deterministic grounding checks verify amounts, counterparties, rule names and sanctions wording against the evidence loaded from the DB.
- [x] AC-2: Given every claim passes the checks, when the draft is accepted, then investigation.drafted.v1 is written with the narrative.
- [x] AC-3: Given a claim states an amount, counterparty, rule name or sanctions wording not present in the evidence, when it is checked, then the draft is rejected, no narrative is written and the draft is retried.
- [x] AC-4: Given grounding fails on every attempt up to LLM_MAX_ATTEMPTS, when the last attempt fails, then investigation.skipped.v1 with reason grounding_failure is written and no narrative exists for that alert.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_grounding.py (money table, counterparty, rule, sanctions cases) | grounding checks cover amounts, counterparties, rule names, sanctions wording |
| AC-2 | tests/test_grounding.py (test_sum_of_cited_credits_passes_in_finding_and_summary); tests/test_investigator.py (test_stack_drafted_row_stub) | grounded draft is stored |
| AC-3 | tests/test_grounding.py (test_unknown_counterparty_fails, test_rule_not_fired_fails, test_ofac_without_hit_fails_and_with_hit_passes) | ungrounded claim rejected and retried |
| AC-4 | tests/test_llm.py (test_retry_exhausts_to_grounding_failure_with_checks); tests/test_investigator.py (test_stack_ungrounded_is_grounding_failure) | grounding_failure skip after max attempts |
