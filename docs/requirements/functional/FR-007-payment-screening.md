---
id: "FR-007"
title: "Outbound counterparty screening"
type: "functional"
priority: "P1"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["kyc.py", "scoring.py", "sql/003-kyc.sql"]
test_files: ["tests/test_kyc.py"]
depends_on: ["FR-006", "FR-002"]
implements: []
---

# FR-007: Outbound counterparty screening

## Description
Debit counterparties are screened against the active sanctions snapshot, once per (account, normalized name, snapshot), during scoring.

## Requirements

### FR-007.1: Debits only
`payment_screen()` SHALL return without action when direction is not `debit`. (kyc.py:82-83)

**Acceptance Criteria:**
- AC-1: A credit produces no `screened_counterparties` row and no audit row.

### FR-007.2: Once per account/name/snapshot
It SHALL insert `(account, normalize(counterparty), snapshot.version)` into `screened_counterparties` with `ON CONFLICT DO NOTHING`, and SHALL screen and audit only if a row was inserted. (kyc.py:84-90; sql/003-kyc.sql:6-10)

**Acceptance Criteria:**
- AC-1: Two debits to the same (case/order-variant) counterparty on one account yield one `payment.screened.v1` row (test_payment_stream_screens_each_new_counterparty_once).
- AC-2: Same counterparty on a different account, or under a new snapshot hash, is screened again.

### FR-007.3: Audit content
The audit row SHALL be action `payment.screened.v1`, actor `kyc-screen-v1`, with `inputs` = `{account, name, snapshot, threshold, hits}`, `case_id` and `transaction_id` from the triggering transaction. (kyc.py:45-49, 90)

**Acceptance Criteria:**
- AC-1: `inputs.account` is present and `transaction_id` equals the triggering transaction.
- AC-2: A clean counterparty still records a row with empty `hits`.

### FR-007.4: Recording only
Screening SHALL NOT alter the score, block, or close anything; it runs in the scorer's DB transaction before the score lookup. (scoring.py:32-33)

**Acceptance Criteria:**
- AC-1: A transaction to a sanctioned counterparty has the same score as an otherwise identical clean one.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-007.1 | none directly | kyc.py:82-83 |
| FR-007.2 | tests/test_kyc.py::test_payment_stream_screens_each_new_counterparty_once | kyc.py:84-90 |
| FR-007.3 | tests/test_kyc.py | kyc.py:45-49 |
| FR-007.4 | none directly | scoring.py:32-33 |
