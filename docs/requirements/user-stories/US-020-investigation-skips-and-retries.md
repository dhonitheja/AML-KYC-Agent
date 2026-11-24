---
id: "US-020"
title: "Bad alerts are skipped and model failures retried"
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
test_files: ["tests/test_eval_scenarios.py", "tests/test_investigator.py", "tests/test_llm.py"]
epic: "investigation-agent"
---

# US-020: Bad alerts are skipped and model failures retried

## Story
As a **platform engineer**, I want **malformed or unresolvable alerts to be skipped and model failures retried**, so that **one bad message never causes a crash loop or a half-written narrative**.

## Acceptance Criteria
- [x] AC-1: Given a malformed alert, an unknown transaction_id, or a transaction with no alerted.v1 row, when it is consumed, then an investigation.skipped.v1 audit event is written with audit.transaction_id NULL (it is an FK), inputs.reason in {malformed_alert, unknown_transaction, not_alerted}, inputs.alert_key = "alerts:<partition>:<offset>" (Kafka origin) for these three reasons, and inputs.origin {topic, partition, offset}, and consumption continues.
- [x] AC-2: Given the same bad alert is redelivered, when it is consumed again, then exactly one skipped row exists (unique on inputs->>'alert_key'). unknown_transaction and not_alerted skips are keyed by Kafka origin, not transaction_id, so they cannot block a later valid alert.
- [x] AC-3: Given a model error, timeout, or a draft citing ids outside the evidence, when the draft is attempted, then no narrative is written and it is retried up to LLM_MAX_ATTEMPTS (default 3) times.
- [x] AC-4: Given LLM_MAX_ATTEMPTS failed attempts, when the last fails, then investigation.skipped.v1 with reason model_failure, inputs.alert_key = the alert's transaction_id (mutually exclusive with a draft) and inputs.origin, is written and the offset committed, with no infinite retry or crash loop. When attempts fail for different reasons, the skip records the reason of the last failed attempt: a model error, timeout, schema failure or citation failure gives model_failure.
- [x] AC-5: Given grounding checks fail on every attempt (US-023), when the last attempt fails, then investigation.skipped.v1 with reason grounding_failure, inputs.alert_key = the alert's transaction_id (so it is mutually exclusive with a draft for that transaction) and inputs.origin, is written and the offset committed. When attempts fail for different reasons, the skip records the reason of the last failed attempt: a grounding check failure gives grounding_failure.
- [x] AC-6: Given an alert whose evidence list is long, when the evidence is built, then it is truncated and the investigation proceeds; it is not skipped or rejected.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_unknown_transaction, test_stack_malformed_alert, test_stack_forged_then_genuine) | skipped event with NULL transaction_id and reason in inputs |
| AC-2 | tests/test_investigator.py (test_stack_unknown_transaction) | one skipped row on redelivery |
| AC-3 | tests/test_llm.py (test_retry_exhausts_to_model_failure); tests/test_investigator.py (test_stack_forced_raise_skip_and_redelivery, test_stack_fabricated_citation_is_model_failure) | bounded retries on error, timeout or out-of-evidence citations |
| AC-4 | tests/test_llm.py (test_retry_exhausts_to_model_failure); tests/test_investigator.py (test_stack_forced_raise_skip_and_redelivery) | model_failure skip written and committed after max attempts; last failed attempt's reason recorded |
| AC-5 | tests/test_llm.py (test_retry_exhausts_to_grounding_failure_with_checks); tests/test_investigator.py (test_stack_ungrounded_is_grounding_failure) | grounding_failure skip written and committed; last failed attempt's reason recorded |
| AC-6 | tests/test_investigator.py (test_build_evidence_truncates_long_rule_lists); tests/test_eval_scenarios.py (test_many_credit_ids_truncated_and_citations_checked_against_sent_ids) | long evidence truncated, not skipped |
