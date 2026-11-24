---
id: "FR-011"
title: "Hallucination and grounding controls"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.2"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["grounding.py", "investigator.py", "llm.py", "eval_investigator.py", "tests/eval/scenarios.json"]
test_files: ["tests/test_grounding.py", "tests/test_eval_scenarios.py", "tests/test_investigator.py", "tests/test_llm.py"]
depends_on: ["FR-009", "FR-010", "NFR-005"]
implements: []
---

# FR-011: Hallucination and grounding controls (Phase 4, built)

## Description
Controls that keep the investigation agent's narrative (FR-009) grounded in gathered evidence: claim-level output, deterministic checks in code before any write (no second model call), a consistency flag, mandatory labeling, and a versioned evaluation set for model validation (SR 11-7). Requested at Design sign-off. The agent stays recommend-only (NFR-005).

## Requirements

### FR-011.1: Claim-level output
The model output SHALL include `findings` in addition to `summary` and `recommendation`: a list of 1..10 entries, each `{statement, cited_transaction_ids, rule}` where `statement` is at most 300 characters, `cited_transaction_ids` is non-empty and a subset of the evidence transaction ids, and `rule` is optional but, when present, SHALL be a rule present in the alert's `scored.v1` rules. Every transaction id cited in the summary or draft SHALL appear in at least one finding.

**Acceptance Criteria:**
- AC-1: Output with zero or more than 10 findings is rejected (counts as a failed attempt).
- AC-2: A finding with a statement over 300 characters, empty `cited_transaction_ids`, an id outside the evidence, or a `rule` not in the alert's `scored.v1` rules is rejected.
- AC-3: A summary citing an id that appears in no finding is rejected.

### FR-011.2: Deterministic grounding checks
Before any audit write, the service SHALL run these checks in code, with no second model call:
- (a) every `$`-prefixed money amount stated in the summary or findings (e.g. "$80,900" or "$80,900.00") equals, in integer cents, the `amount_cents` of an evidence transaction or the sum of the cited transactions' amounts; a `$` followed by digits that does not parse as a whole amount with 0 or 2 decimals fails. The prompt SHALL require money written as `$X,XXX.XX`. Amounts written without `$` are not checked (accepted residual, RR-21), because bare decimals cannot be told apart from screening scores;
- (b) every counterparty name mentioned matches an evidence counterparty (after normalization);
- (c) every rule name mentioned is in the alert's fired rules;
- (d) wording claiming a sanctions/screening match ("sanction", "OFAC", "SDN", "watchlist match", "screening hit") appears only if a screening hit exists in the evidence.

A failed check SHALL count as a failed attempt (retry up to `LLM_MAX_ATTEMPTS`, FR-010.4). Skip reasons: a model error, timeout, schema-invalid output, or citation-subset violation (FR-009.4, FR-011.1) is a `model_failure`; a failure of grounding checks (a)-(d) is a `grounding_failure`; both count toward `LLM_MAX_ATTEMPTS`. If all attempts fail, the service SHALL write `investigation.skipped.v1` with `inputs.reason` equal to the reason of the LAST failed attempt; when that is `grounding_failure`, the failed check names are stored in `inputs.failed_checks`.

**Acceptance Criteria:**
- AC-1: A draft stating an amount not in the evidence (e.g. "$81,000" when only $80,900.00 exists) fails check (a); "$100000" is read as $100,000.00, not truncated to $100; "$5.5" fails as malformed; "sent $80,900.50, then" is read whole as $80,900.50; a draft stating the sum of the cited credits passes; an amount written without "$" (e.g. "80900.00") is not checked (accepted residual, RR-21).
- AC-2: A draft naming a counterparty absent from the evidence fails check (b).
- AC-3: A draft naming a rule that did not fire fails check (c).
- AC-4: A draft saying "OFAC match" with no screening hit in evidence fails check (d); the same wording with a screening hit passes.
- AC-5: The stub model returning ungrounded output on every attempt yields exactly `LLM_MAX_ATTEMPTS` attempts, no drafted row, and one skipped row with `reason = grounding_failure` and the failed check names.
- AC-6: The checks make no model call (model call count unchanged by checking).
- AC-7: When attempts fail for different reasons (grounding failure, then model error on the last attempt), the skipped row has `reason = model_failure`; with the order reversed it has `reason = grounding_failure` and `failed_checks` (FR-010.4 AC-5).

### FR-011.3: Consistency flag
If the recommendation is `no_further_action_suggested` while the evidence contains a rule with points >= 60 or any screening hit, the drafted row SHALL carry `inputs.consistency_warning = true` and `inputs.consistency_reason`. The recommendation SHALL NOT be overridden (recommend-only, NFR-005).

**Acceptance Criteria:**
- AC-1: `no_further_action_suggested` with a rule of 60 points yields a drafted row with `consistency_warning = true`, a reason, and the recommendation unchanged.
- AC-2: `no_further_action_suggested` with a screening hit in evidence yields the same flag.
- AC-3: `escalate_for_review`, or `no_further_action_suggested` with neither condition, carries no warning (or `false`).

### FR-011.4: Labeling
Every drafted row SHALL carry `inputs.ai_generated = true`, `inputs.requires_human_review = true`, and `inputs.grounding = {checks: [names], passed: true, attempts}`.

**Acceptance Criteria:**
- AC-1: Every `investigation.drafted.v1` row contains the three fields with the stated values.
- AC-2: `grounding.checks` lists the names of all executed checks and `attempts` is the number of model attempts used (1..`LLM_MAX_ATTEMPTS`).

### FR-011.5: Evaluation set (SR 11-7 model validation)
A versioned set of at least 8 synthetic scenarios with expected outcomes SHALL exist: AML-1042 pass-through; clean low-risk; a screening hit; a large cash transfer; a counterparty name containing a prompt-injection string; a malformed alert; an alert with >= 60 credit ids (FR-009 W1); and a forged alert for a non-alerted transaction (FR-009 W2). In CI with the stub model all expected outcomes SHALL match. An opt-in script SHALL run the set against the real model (`LLM_MODE=anthropic`) and report grounding-failure rate, citation-violation rate and recommendation agreement, without writing to the production audit.

**Acceptance Criteria:**
- AC-1: The set is versioned, contains >= 8 scenarios covering the eight named cases, each with an expected outcome (drafted/skipped, reason, recommendation).
- AC-2: In CI with the stub model, every scenario's actual outcome equals its expected outcome (no API key needed).
- AC-3: The opt-in script reports the three rates and refuses to run unless `LLM_MODE=anthropic` and `DATA_CLASSIFICATION=synthetic` (FR-010.6, NFR-008.3(a)).
- AC-4: Running the script leaves the production `audit` table unchanged (row count identical before and after).
- AC-5: The prompt-injection scenario produces no instruction-following behavior: output remains schema-valid and grounded, or is skipped as `grounding_failure`.

## Traceability
| Sub-req | Test file (test names) | Source reference |
|---------|-----------|-----------------|
| FR-011.1 | tests/test_grounding.py (test_finding_count_out_of_range_rejected, test_statement_length_boundary, test_empty_citations_rejected, test_summary_id_missing_from_findings_rejected) | grounding.py `Draft`, `Finding` |
| FR-011.2 | tests/test_grounding.py (19-case money table, counterparty, rule, sanctions, test_check_grounding_makes_no_model_call); tests/test_llm.py (test_retry_exhausts_to_grounding_failure_with_checks, test_retry_last_reason_follows_last_attempt) | grounding.py `check_grounding`, llm.py `complete_with_retry` |
| FR-011.3 | tests/test_grounding.py (test_consistency_*); tests/test_investigator.py (test_build_drafted_row_consistency_warning) | grounding.py `consistency` |
| FR-011.4 | tests/test_investigator.py (test_build_drafted_row_labels, test_stack_drafted_row_stub) | investigator.py `build_drafted_row` |
| FR-011.5 | tests/test_eval_scenarios.py (AC-1, AC-2, AC-5; test_eval_script_imports_no_psycopg for AC-4; test_eval_refuses_unless_anthropic_and_synthetic for the AC-3 gate). The AC-3 rate report against a real model is not exercised by any automated test | eval_investigator.py, tests/eval/scenarios.json |

## Change Notes
- v1.1 (2026-11-23, NFR-008 delta): FR-011.5 AC-3 also requires `DATA_CLASSIFICATION=synthetic`.
- v1.2 (2026-11-24, Requirements Sync, PLAN-002): promoted to implemented; source_files/test_files filled. No requirement text changed.
