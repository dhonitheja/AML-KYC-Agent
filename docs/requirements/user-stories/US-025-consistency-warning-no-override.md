---
id: "US-025"
title: "Analyst sees a consistency warning and the recommendation stands"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-011"]
implements_nfr: ["NFR-005"]
test_files: ["tests/test_grounding.py", "tests/test_investigator.py"]
epic: "investigation-agent"
---

# US-025: Analyst sees a consistency warning and the recommendation stands

## Story
As an **AML compliance analyst**, I want **a consistency_warning when the draft says no further action against strong evidence**, so that **I look closer while the model's recommendation stays untouched for me to decide**.

## Acceptance Criteria
- [x] AC-1: Given a draft recommends no_further_action_suggested and the evidence has a rule scoring 60 points or more, when it is checked, then a consistency_warning is recorded on the drafted row.
- [x] AC-2: Given a draft recommends no_further_action_suggested and the evidence has a screening hit, when it is checked, then a consistency_warning is recorded on the drafted row.
- [x] AC-3: Given a consistency_warning is raised, when the row is stored, then the recommendation is exactly what the model produced and is never overridden or replaced.
- [x] AC-4: Given no conflict exists, when the draft is stored, then no consistency_warning is present.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_grounding.py (test_consistency_warns_on_high_points) | warning on >=60-point rule conflict |
| AC-2 | tests/test_grounding.py (test_consistency_warns_on_screening_hit) | warning on screening-hit conflict |
| AC-3 | tests/test_grounding.py (test_consistency_warns_on_high_points); tests/test_investigator.py (test_build_drafted_row_consistency_warning) | recommendation unchanged |
| AC-4 | tests/test_grounding.py (test_consistency_no_warning_cases) | no warning when consistent |
