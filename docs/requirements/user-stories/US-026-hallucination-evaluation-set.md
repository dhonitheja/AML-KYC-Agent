---
id: "US-026"
title: "Model risk officer runs the hallucination evaluation set"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "model risk officer"
implements_fr: ["FR-011"]
implements_nfr: ["NFR-004", "NFR-006"]
test_files: ["tests/conftest.py", "tests/egress_check.py", "tests/eval/scenarios.json", "tests/test_eval_scenarios.py"]
epic: "investigation-agent"
---

# US-026: Model risk officer runs the hallucination evaluation set

## Story
As a **model risk officer**, I want **to run an evaluation set of synthetic scenarios and get hallucination metrics**, so that **I can measure model risk before and after a model or prompt change**.

## Acceptance Criteria
- [x] AC-1: Given the evaluation set, when I inspect it, then it holds at least 8 synthetic scenarios and no real customer data (NFR-006).
- [x] AC-2: Given no model key, when the stub run executes in CI, then it completes and passes.
- [ ] AC-3: Given I opt in to a real-model run, when it completes, then it reports hallucination metrics.
- [x] AC-4: Given the real-model run is not opted in, when CI runs, then no real model is called.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_eval_scenarios.py (test_scenario_file_is_versioned_and_complete, test_every_fixture_id_is_a_uuid) | at least 8 synthetic scenarios |
| AC-2 | tests/test_eval_scenarios.py (test_stub_outcome_matches_expected); CI pytest step | stub run passes in CI |
| AC-3 | eval_investigator.py report (opt-in, real model); only the refusal gate is tested: tests/test_eval_scenarios.py (test_eval_refuses_unless_anthropic_and_synthetic). Report metrics UNVERIFIED | opt-in real-model run reports metrics |
| AC-4 | tests/conftest.py guard; tests/egress_check.py (CI) no-route probe in CI | CI makes no real model call |
