---
id: "US-027"
title: "A forged alert cannot block or fabricate an investigation"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-009"]
implements_nfr: ["NFR-003"]
test_files: ["tests/test_eval_scenarios.py", "tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-027: A forged alert cannot block or fabricate an investigation

## Story
As a **platform engineer**, I want **the investigator to act only on alerts backed by the audit table and to build evidence from the DB**, so that **a forged Kafka message can neither suppress a real investigation nor create a fake one**.

## Acceptance Criteria
- [x] AC-1: Given an alert message whose transaction has no alerted.v1 row, when it is consumed, then no investigation is drafted and investigation.skipped.v1 with reason not_alerted is written.
- [x] AC-2: Given an alert message whose payload differs from the DB, when evidence is built, then it comes from the DB and the Kafka payload content is not used.
- [x] AC-3: Given a forged alert for a real transaction that has an alerted.v1 row, when it is consumed, then the narrative is drafted from DB evidence only.
- [x] AC-4: Given a forged or bad alert, when its skip is recorded, then the malformed_alert, unknown_transaction and not_alerted skips are keyed by Kafka origin so they cannot block a later real alert for the same transaction_id. model_failure and grounding_failure skips for a genuine alerted transaction are keyed by transaction_id.
- [x] AC-5: Given the real alert for that transaction arrives after a forged one, when it is consumed, then its investigation is drafted normally.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_forged_then_genuine); tests/test_eval_scenarios.py (test_forged_alert_never_reaches_model) | not_alerted skip, no draft |
| AC-2 | tests/test_investigator.py (test_stack_payload_rules_ignored, test_build_evidence_rules_from_db_not_payload) | evidence from DB, not Kafka payload |
| AC-3 | tests/test_investigator.py (test_stack_payload_rules_ignored) | forged payload for alerted transaction uses DB evidence |
| AC-4 | tests/test_investigator.py (test_build_skipped_row_origin_keyed, test_stack_unknown_transaction, test_stack_malformed_alert) | malformed_alert / unknown_transaction / not_alerted skips keyed by origin; model_failure / grounding_failure skips keyed by transaction_id |
| AC-5 | tests/test_investigator.py (test_stack_forged_then_genuine) | real alert after forged one still investigated |
