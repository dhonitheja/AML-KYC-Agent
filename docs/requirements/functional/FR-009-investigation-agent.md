---
id: "FR-009"
title: "Alert investigation agent"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.2"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["investigator.py", "llm.py", "grounding.py", "sql/004-investigation.sql", "compose.yaml", "compose.anthropic.yaml", ".github/workflows/ci.yml", "scoring.py", "kyc.py", "sql/002-scoring.sql"]
test_files: ["tests/test_investigator.py", "tests/test_eval_scenarios.py", "tests/conftest.py", "tests/eval/scenarios.json"]
depends_on: ["FR-004", "FR-007", "FR-010", "FR-011"]
implements: []
---

# FR-009: Alert investigation agent (Phase 4, built)

## Description
A new compose service consumes the `alerts` topic and drafts a case narrative for each alert from gathered evidence, recording it as one versioned audit event. It is advisory: it never clears, blocks, closes cases or alters scores. Existing patterns reused: replay check (scoring.py:34-37), partial unique index (sql/002-scoring.sql:3-4), idempotent migrate (compose.yaml:34-41).

## Change notes
- v1.2 (2026-11-24, Requirements Sync, PLAN-002): promoted to implemented; source_files/test_files filled from the shipped code. No requirement text changed.
- v1.1: Amendments for hallucination controls (FR-011, claim-level findings, grounding checks, labeling), W1 (long evidence lists truncated, FR-009.10) and W2 (alert authenticity, FR-009.9; Kafka-origin `alert_key` and NULL `audit.transaction_id` for malformed, unknown and not-alerted skips, FR-009.7).

## Requirements

### FR-009.1: Consumer
The service SHALL consume `alerts` under stable group `aml-investigator-v1` (auto-commit off, `earliest`), and SHALL be added to compose with `depends_on` migrate and topic. It SHALL commit offsets only after its DB transaction commits.

**Acceptance Criteria:**
- AC-1: Consumer config has group `aml-investigator-v1` and auto-commit disabled.
- AC-2: Killing the process before DB commit causes redelivery with no lost investigation.

### FR-009.2: Evidence gathering
For each alert the service SHALL, by `transaction_id`, load: the transaction and its account from `transactions`; the account's transaction history (ids, counterparty, amount, direction, channel, time); the `scored.v1` rule evidence; and `payment.screened.v1` rows for that account (kyc.py:88-90 inputs carry `account`).

**Acceptance Criteria:**
- AC-1: For the seeded AML-1042 alert, evidence contains the two credit ids and the debit id.
- AC-2: Screening hits in evidence carry the snapshot hash.
- AC-3: Rules and score in evidence come from the DB `scored.v1` row; a Kafka payload carrying different rules or score does not change the evidence (W2, FR-009.9).

### FR-009.3: Narrative output
The service SHALL INSERT one audit row, action `investigation.drafted.v1`, actor `investigator-v1`, `model_version` and `prompt_version` populated, `case_id` read from the DB `scored.v1` row, never from the Kafka payload (for a genuine alert it equals the alert's; NULL except AML-1042), `transaction_id` set. `inputs` SHALL be JSON with: `summary` text; `recommendation` in {`escalate_for_review`, `no_further_action_suggested`}; `cited_transaction_ids`; `findings` and the labeling/grounding fields defined in FR-011; and an evidence snapshot (rules, history ids, screening hits with snapshot hash).

**Acceptance Criteria:**
- AC-1: Row has non-null model_version and prompt_version.
- AC-2: `recommendation` outside the two values is rejected and not stored.
- AC-3: Evidence snapshot is stored alongside the narrative.

### FR-009.4: Citation integrity
`cited_transaction_ids` SHALL be a subset of the transaction ids in the gathered evidence. A draft citing any other id SHALL be treated as invalid (not stored; handled as a model failure per FR-010.4).

**Acceptance Criteria:**
- AC-1: Injecting a fabricated id from the model yields no `investigation.drafted.v1` row.

### FR-009.5: At most one draft per transaction
Outcome invariant: at most one `investigation.drafted.v1` per alert `transaction_id`; every consumed alert ends with exactly one drafted or skipped record. A new idempotent `sql/004` migration SHALL create a partial unique index on `audit(transaction_id) WHERE action='investigation.drafted.v1'` and SHALL be added to the `migrate` command. Before any model call the service SHALL check for an existing row (pattern scoring.py:34-37) and skip the alert (no model call, no new row, commit offset) if EITHER an `investigation.drafted.v1` row exists for its `transaction_id` OR an `investigation.skipped.v1` row exists for its `alert_key` (FR-009.7); the INSERT SHALL use `ON CONFLICT DO NOTHING` as a backstop. Drafted rows (unique on `transaction_id`) and skipped rows (unique on `alert_key`) are each DB-enforced by partial unique indexes. Drafted rows also carry `inputs.alert_key` = `transaction_id`, and one partial unique index on `inputs->>'alert_key'` across both actions makes the two outcomes mutually exclusive at the database level. The pre-check only avoids redundant model calls. The investigator's database role SHALL have only SELECT/INSERT (no UPDATE/DELETE), bounded as in NFR-003.

**Acceptance Criteria:**
- AC-1: Delivering the same alert twice produces one row and the model is called once.
- AC-2: Running migrations twice succeeds.
- AC-3: A direct duplicate insert violates the index.
- AC-4: Given an alert previously skipped with reason `model_failure`, When it is redelivered, Then no model call is made and no audit row is added.

### FR-009.6: Recommend-only
The service SHALL NOT write to `cases`, UPDATE/DELETE any row, publish to `transactions`/`alerts`, or modify `scored.v1`/`alerted.v1`.

**Acceptance Criteria:**
- AC-1: After investigation the `scored.v1` and `alerted.v1` rows are byte-identical.
- AC-2: DB role lacks UPDATE/DELETE privilege.

### FR-009.7: Skipped alerts
If the alert's `transaction_id` is not found, the transaction is not alerted (FR-009.9), the payload is malformed, the model fails (FR-010.4), or grounding fails (FR-011.2), the service SHALL record a skipped audit event (`investigation.skipped.v1`) and commit the offset rather than crash-loop. Because `audit.transaction_id` is a foreign key to `transactions` (sql/001-foundations.sql:18), skipped rows for `malformed_alert`, `unknown_transaction` and `not_alerted` SHALL set `audit.transaction_id = NULL` (a forged message is never linked to a real transaction); skipped rows for `model_failure` and `grounding_failure` SHALL set `transaction_id` to the alert's transaction id. The raw alert transaction id SHALL be stored under `inputs.alert_transaction_id` (may be null for malformed alerts) and `inputs.reason` SHALL be one of `malformed_alert`, `unknown_transaction`, `not_alerted`, `model_failure`, `grounding_failure`.

Every `investigation.skipped.v1` row SHALL store `inputs.alert_key` and `inputs.origin = {topic, partition, offset}`. For reasons `malformed_alert`, `unknown_transaction` and `not_alerted`, `alert_key` SHALL be `"alerts:<partition>:<offset>"` (Kafka origin), so a forged alert cannot occupy a real transaction's slot. For `model_failure` and `grounding_failure` (the transaction exists and is alerted) and for drafted rows, `alert_key` = the alert's `transaction_id`.

Skipped rows SHALL be deduplicated: `sql/004` SHALL add the partial unique index `audit_investigation_alert_once` on `((inputs->>'alert_key')) WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1')`, which covers skipped rows and also makes drafted and skipped mutually exclusive (ADR-023), and the insert SHALL use `ON CONFLICT DO NOTHING`.

**Acceptance Criteria:**
- AC-1: Alert with unknown transaction_id yields one `investigation.skipped.v1` row and the consumer continues.
- AC-2: Non-JSON payload does not crash the service and records `inputs.reason = malformed_alert`.
- AC-3: A skipped row for an unknown transaction has `transaction_id` NULL, `inputs.alert_transaction_id` equal to the raw id, and `inputs.reason = unknown_transaction`; the insert does not violate the FK.
- AC-4: A redelivered bad alert, with or without a parseable transaction id, yields exactly one `investigation.skipped.v1` row.
- AC-5: Every skipped row has `inputs.alert_key` and `inputs.origin` {topic, partition, offset}; for `malformed_alert`, `unknown_transaction` and `not_alerted` the `alert_key` is `alerts:<partition>:<offset>`; for `model_failure` and `grounding_failure` it is the `transaction_id`.
- AC-6: `inputs.reason` is always one of {malformed_alert, unknown_transaction, not_alerted, model_failure, grounding_failure}; any other value is not stored.
- AC-7: For `malformed_alert`, `unknown_transaction` and `not_alerted`, `audit.transaction_id` and `audit.case_id` are NULL even when the raw payload names an existing transaction or case; for `model_failure` and `grounding_failure`, `audit.transaction_id` is set and equals `inputs.alert_key`.

### FR-009.8: Known limitation
There is no account-to-KYC-application link (`kyc_applications` has no account column; onboarding audit rows have NULL case_id/transaction_id). Onboarding KYC evidence is OUT OF SCOPE; screening evidence is limited to `payment.screened.v1`. No new API endpoint is required in this phase (results are read from `audit`).

**Acceptance Criteria:**
- AC-1: Evidence snapshot contains no onboarding data.

### FR-009.9: Alert authenticity (W2, forged alerts)
The investigator SHALL act only if an `alerted.v1` audit row exists for the alert's `transaction_id`. Evidence (rules, score) SHALL come from the DB `scored.v1` row, never from the Kafka payload. An alert whose transaction does not exist SHALL be skipped as `unknown_transaction`; one whose transaction exists but has no `alerted.v1` row SHALL be skipped as `not_alerted`; both use `alert_key = "alerts:<partition>:<offset>"` (the Kafka origin) and `audit.transaction_id = NULL` (FR-009.7). A real alert for an existing, alerted transaction keeps `alert_key = transaction_id`.

**Acceptance Criteria:**
- AC-1: A forged alert for an existing transaction with no `alerted.v1` row yields no model call and one skipped row with `reason = not_alerted`, `alert_key = alerts:<partition>:<offset>`, and `audit.transaction_id` NULL.
- AC-2: After a forged alert for transaction T is processed, a later real alert for T is still investigated (its `alert_key = T` slot is not occupied).
- AC-3: An alert payload with rules/score differing from `scored.v1` yields evidence matching `scored.v1`.

### FR-009.10: Long evidence lists (W1)
Rule evidence lists of any length SHALL be accepted. Evidence sent to the model SHALL be truncated to at most 50 ids per rule, keeping the alerted transaction id and the most recent ids, and `inputs` SHALL record `evidence_truncated = true` with the original counts per rule. Rejecting an alert as malformed because of long evidence is not allowed.

**Acceptance Criteria:**
- AC-1: An alert with a rule listing 60 or more credit ids is processed (not `malformed_alert`), the model receives at most 50 ids for that rule: the alerted transaction id if the list contains it, plus the most recent others, and `inputs.evidence_truncated = true` with the original count.
- AC-2: Evidence lists of 50 ids or fewer are sent unchanged and `evidence_truncated` is false or absent.
- AC-3: Citation integrity (FR-009.4) is checked against the ids actually sent to the model.

## Traceability
| Sub-req | Test file (test names) | Source reference |
|---------|-----------|-----------------|
| FR-009.1 | tests/test_investigator.py (test_consumer_config; test_stack_crash_before_commit_then_redelivery) | investigator.py `consumer_config`, `consume` |
| FR-009.2 | tests/test_investigator.py (test_stack_drafted_row_stub, test_build_evidence_screenings_keep_snapshot); tests/test_eval_scenarios.py (test_aml_1042_cites_two_credits_and_debit); CI drafted-row check | investigator.py `build_evidence` |
| FR-009.3, FR-009.4 | tests/test_investigator.py (test_build_drafted_row_labels, test_stack_fabricated_citation_is_model_failure); tests/test_grounding.py (test_validate_draft_rejects_fabricated_ids) | investigator.py `validate_draft`, grounding.py |
| FR-009.5 | tests/test_investigator.py (test_stack_redelivery_dedupes, test_stack_duplicate_insert_violates_index); CI runs `migrate` twice (AC-2) | sql/004-investigation.sql |
| FR-009.6 | tests/test_investigator.py (test_stack_scored_and_alerted_unchanged, test_stack_role_privileges) | sql/004-investigation.sql |
| FR-009.7 | tests/test_investigator.py (test_build_skipped_row_*, test_stack_unknown_transaction, test_stack_malformed_alert) | investigator.py `build_skipped_row` |
| FR-009.8 | tests/test_investigator.py (test_build_evidence_allow_list_and_alias, test_stack_investigator_cannot_read_sensitive_tables) | investigator.py, sql/004-investigation.sql |
| FR-009.9 | tests/test_investigator.py (test_stack_forged_then_genuine, test_stack_payload_rules_ignored); tests/test_eval_scenarios.py (test_forged_alert_never_reaches_model) | investigator.py `decide`, `handle` |
| FR-009.10 | tests/test_investigator.py (test_build_evidence_truncates_long_rule_lists, test_build_evidence_short_lists_unchanged); tests/test_eval_scenarios.py (test_many_credit_ids_truncated_and_citations_checked_against_sent_ids) | investigator.py `build_evidence` |

Original design references: scoring.py:34-37; kyc.py:88-90; sql/002-scoring.sql:3-4; compose.yaml:34-41.
