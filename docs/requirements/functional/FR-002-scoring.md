---
id: "FR-002"
title: "Real-time rule scoring"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["rules.py", "scoring.py", "sql/002-scoring.sql"]
test_files: ["tests/test_rules.py", "latency.py"]
depends_on: ["FR-001", "FR-003"]
implements: []
---

# FR-002: Real-time rule scoring

## Description
Each transaction is scored by a pure function `rules.assess(row, minute_count, hour_count, history)` inside a Quix Streams consumer (group `aml-scorer-v1`). Rules are illustrative, not calibrated policy.

## Requirements

### FR-002.1: Seven rules with fixed points
`assess` SHALL evaluate: rapid_pass_through (65; debit within 75-125% of prior 48h credit inflows), large_single_transfer (35; >= 10,000,000 cents), large_cash_activity (25; channel cash, >= 500,000), minute_velocity (35; count >= 10), hour_velocity (25; count >= 40), repeated_amount (30; >= 2 prior matches on direction+amount+channel), multiple_credit_sources (30; debit with >= 4 distinct credit counterparties). Each hit SHALL carry `rule`, `points`, `evidence` (transaction ids / text). (rules.py:12-28)

**Acceptance Criteria:**
- AC-1: The seed scenario's debit hits rapid_pass_through with evidence = both credit ids + the debit id (test_northstar_pass_through).
- AC-2: Each remaining rule triggers at its threshold (test_remaining_rules checks at-threshold values only); not triggering below threshold: none (gap).

### FR-002.2: Score cap and alert threshold
Score SHALL be `min(100, sum(points))`; `alert` SHALL be true iff score >= 60. Result SHALL be `{transaction_id, case_id, run_id, version:"v1", score, alert, rules}`. (rules.py:29-31)

**Acceptance Criteria:**
- AC-1: Combined hits never exceed 100.
- AC-2: rapid_pass_through alone (65) alerts; large_single_transfer alone (35) does not.

### FR-002.3: 48-hour scored history
History SHALL be the account's transactions in [occurred_at-48h, occurred_at] that already have a `scored.v1` audit row, ordered by `occurred_at, id`. (scoring.py:40-43)

**Acceptance Criteria:**
- AC-1: An unscored earlier transaction is excluded from history.
- AC-2: A transaction older than 48h is excluded.

### FR-002.4: Single transaction per message and replay reuse
Per message, the scorer SHALL in one DB transaction: record_transaction, payment_screen, check for an existing `scored.v1`; if present SHALL return its stored `inputs` without re-scoring or re-counting; otherwise compute velocity, history, `assess`, and insert `scored.v1` (plus `alerted.v1` when alerting) with actor `scorer-v1`. (scoring.py:30-50)

**Acceptance Criteria:**
- AC-1: Redelivering a message yields no second `scored.v1`/`alerted.v1` row (audit_score_once, sql/002-scoring.sql:4).
- AC-2: The replayed output equals the original stored result.

### FR-002.5: Alert-latency gate
End-to-end alert latency (seed to alert on `alerts` topic) SHALL have p95 < 500 ms over 40 scenarios, measured by `latency.py`. (latency.py:44-48; run by .github/workflows/ci.yml:12)

**Acceptance Criteria:**
- AC-1: `latency.py` exits non-zero when p95 >= 500 ms.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-002.1 | tests/test_rules.py | rules.py:12-28 |
| FR-002.2 | tests/test_rules.py | rules.py:29-31 |
| FR-002.3 | none (gap) | scoring.py:40-43 |
| FR-002.4 | none (gap) | scoring.py:30-50; sql/002-scoring.sql:4 |
| FR-002.5 | latency.py; .github/workflows/ci.yml:12 | latency.py:44-48 |
