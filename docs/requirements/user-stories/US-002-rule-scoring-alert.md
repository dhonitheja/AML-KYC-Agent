---
id: "US-002"
title: "Score transactions and raise alerts at 60 or above"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-002"]
implements_nfr: ["NFR-001"]
test_files: ["tests/test_rules.py"]
epic: "detection"
---

# US-002: Score transactions and raise alerts at 60 or above

## Story
As an **AML compliance analyst**, I want **each transaction scored by seven rules with an alert at score 60 or higher**, so that **I can review suspicious activity such as the AML-1042 pass-through**.

## Acceptance Criteria
- [ ] AC-1: Given two credits totalling $83,800 then an $80,900 debit, when the debit is assessed, then rapid_pass_through fires (65 points) and alert is true.
- [ ] AC-2: Given any combination of rules, when points are summed, then the score is capped at 100.
- [ ] AC-3: Given the seed scenario, when seed totals are computed, then they match the documented figures.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_rules.py::test_northstar_pass_through | rapid_pass_through fires (65 points) and alert is true |
| AC-2 | tests/test_rules.py::test_remaining_rules | the score is capped at 100 |
| AC-3 | tests/test_rules.py::test_seed_totals | they match the documented figures |
