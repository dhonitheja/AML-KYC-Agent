---
id: "US-016"
title: "Analyst reads a drafted narrative for AML-1042"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-009"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_eval_scenarios.py", "tests/test_grounding.py", "tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-016: Analyst reads a drafted narrative for AML-1042

## Story
As an **AML compliance analyst**, I want **a drafted case narrative for alert AML-1042 that cites the pass-through evidence, read from the audit table (no new API endpoint this phase)**, so that **I can start the investigation quickly and verify every claim**.

## Acceptance Criteria
- [x] AC-1: Given alert AML-1042 with rapid_pass_through evidence, when the investigation agent runs, then an investigation.drafted.v1 audit row (actor investigator-v1) holds a narrative built from account history, rule evidence and payment.screened.v1 hits.
- [x] AC-2: Given the narrative, when it is read, then it cites the two credits ($83,800) and the $80,900 debit by evidence id.
- [x] AC-3: Given any claim in the narrative, when it is validated, then it cites only evidence ids that were gathered, and a narrative citing unknown ids is rejected.
- [x] AC-4: Given an account with no payment.screened.v1 rows, when the narrative is drafted, then it reports no screening hits; onboarding KYC findings are not linked to accounts (known limitation, out of scope).

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_drafted_row_stub); CI drafted-row check | an investigation.drafted.v1 audit row (actor investigator-v1) holds a  |
| AC-2 | tests/test_eval_scenarios.py (test_aml_1042_cites_two_credits_and_debit) | it cites the two credits ($83,800) and the $80,900 debit by evidence i |
| AC-3 | tests/test_grounding.py (test_validate_draft_rejects_fabricated_ids); tests/test_investigator.py (test_stack_fabricated_citation_is_model_failure) | it cites only evidence ids that were gathered, and a narrative citing  |
| AC-4 | tests/test_investigator.py (test_build_evidence_without_screenings); tests/test_eval_scenarios.py (test_clean_scenario_has_no_hit_wording_and_no_onboarding_keys) | it reports no screening hits; onboarding KYC findings are not linked t |
