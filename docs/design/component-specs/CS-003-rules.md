---
id: "CS-003"
title: "Rules: pure risk assessment"
type: "component-spec"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["rules.py"]
satisfies_fr: ["FR-002", "FR-003"]
satisfies_nfr: ["NFR-001", "NFR-004"]
constrained_by_adrs: ["ADR-008", "ADR-009"]
---

# CS-003: rules.py

## Description
Pure function implementing seven illustrative rules (not calibrated policy). No I/O; unit-tested in tests/test_rules.py.

## Public Interface
`assess(row, minute_count, hour_count, history) -> dict` (rules.py:2-31). Returns `{transaction_id, case_id, run_id, version:"v1", score, alert, rules:[{rule, points, evidence}]}`.

## Internal Data Structures
`hits` list of `{rule, points, evidence}`; `history` items `{id, counterparty, amount_cents, direction, channel}`.

## Key Algorithms (rules.py)
| Rule | Points | Condition | Lines |
|---|---|---|---|
| rapid_pass_through | 65 | debit and 0.75*inflows <= amount <= 1.25*inflows (integer math) | 12-13 |
| large_single_transfer | 35 | amount >= 10,000,000 cents | 14-15 |
| large_cash_activity | 25 | channel cash and amount >= 500,000 | 16-17 |
| minute_velocity | 35 | minute_count >= 10 | 18-19 |
| hour_velocity | 25 | hour_count >= 40 | 20-21 |
| repeated_amount | 30 | >= 2 history matches on (direction, amount, channel) | 22-25 |
| multiple_credit_sources | 30 | debit and >= 4 distinct credit counterparties | 26-27 |

Score = `min(100, sum(points))`; `alert = score >= 60` (rules.py:29-31). `rapid_pass_through` alone alerts. Evidence is a list of transaction ids (velocity rules add a count string).

## Component Interactions
Called only by CS-002. Evidence ids it emits are the citation universe used by CS-008.

## Invariants
Deterministic; does not mutate inputs; changing thresholds requires a new `version` string.

## Traceability
FR-002 (rules, threshold 60), FR-003 (velocity inputs); NFR-001, NFR-004 (rule evidence recorded).
