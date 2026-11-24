---
id: "FR-004"
title: "Alert publication and decision audit"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["scoring.py", "sql/001-foundations.sql", "sql/002-scoring.sql", "compose.yaml"]
test_files: ["latency.py"]
depends_on: ["FR-002"]
implements: []
---

# FR-004: Alert publication and decision audit

## Description
Every scoring decision is recorded in the append-only `audit` table; alerting scores are also published to the `alerts` topic.

## Requirements

### FR-004.1: Versioned decision audit rows
The scorer SHALL insert `scored.v1` for every scored transaction and additionally `alerted.v1` when score >= 60, actor `scorer-v1`, `inputs` = full result, `case_id` copied from the row. (scoring.py:45-49)

**Acceptance Criteria:**
- AC-1: Non-alerting transaction has `scored.v1` only; alerting has both.
- AC-2: At most one row per (transaction_id, action) for these actions (audit_score_once).

### FR-004.2: alerts topic publication
Results with `alert == true` SHALL be published as JSON to topic `alerts`. The topic SHALL be created by the one-shot `topic` compose service. (scoring.py:53; compose.yaml:11-16)

**Acceptance Criteria:**
- AC-1: After the seed scenario an alert for the AML-1042 debit appears on `alerts`.
- AC-2: Non-alert results are not published.

### FR-004.3: Payload schema
The alert message SHALL equal the `scored.v1` inputs: `{transaction_id, case_id, run_id, version, score, alert, rules:[{rule, points, evidence}]}` and SHALL NOT include an account field. (rules.py:30-31)

**Acceptance Criteria:**
- AC-1: Payload keys match the list above exactly; an alert carries rapid_pass_through for the seed scenario (latency.py:30).
- AC-2: Account is obtainable only by joining `transactions` on `transaction_id`.

### FR-004.4: At-least-once delivery
Publication occurs after the DB commit; duplicates are possible. Consumers SHALL dedupe by `transaction_id` and `version`. (CLAUDE.md architecture; scoring.py:52-53)

**Acceptance Criteria:**
- AC-1: Replaying an input message does not create a second DB alert row, though a duplicate topic message is permitted.

### FR-004.5: Case linkage
`audit.case_id` SHALL be NULL except for seeded case `AML-1042`, enforced by FK to `cases`; `aml_worker` SHALL NOT be able to INSERT into `cases`. (sql/001-foundations.sql:7,17,21-22)

**Acceptance Criteria:**
- AC-1: Inserting audit with unknown case_id fails.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-004.1 | none (gap) | scoring.py:45-49 |
| FR-004.2 | latency.py; CI `/alerts` check | scoring.py:53; compose.yaml:11-16 |
| FR-004.3 | latency.py:30 (rapid_pass_through only) | rules.py:30-31 |
| FR-004.4 | none (design property) | scoring.py:52-53 |
| FR-004.5 | none directly | sql/001-foundations.sql:7,17,21-22 |
