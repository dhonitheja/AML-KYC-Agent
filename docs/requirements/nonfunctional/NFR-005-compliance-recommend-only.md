---
id: "NFR-005"
title: "Automated components recommend only"
type: "nonfunctional"
category: "compliance"
focus_track: "security"
priority: "P0"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["README.md", "kyc.py", "scoring.py", "rules.py"]
test_files: []
verification_method: "code-review"
---

# NFR-005: Automated components recommend only

Focus track: security (ISO/IEC 27001 governance and compliance). Also supports Responsible AI human oversight.

## Description
Automated components only record findings and recommendations; the human analyst makes every case decision.

## Requirements
- Screeners and the scorer SHALL only record findings and recommendations; none SHALL clear, block or close a case (`README.md:39`). (Phase 4, FR-009/FR-010/FR-011, built) The same SHALL apply to the Phase 4 agent. `aml_worker` cannot update cases (see NFR-003).
- Name-similarity hits identify candidates for analyst review; the human analyst makes the decision.
- (Phase 4, FR-009/FR-010/FR-011, built) Phase 4 narratives SHALL be labelled as recommendations and SHALL NOT alter scores or alert state. A `consistency_warning` SHALL never override the recommendation (FR-011).

## Verification Method
Code review of `README.md:39`, `kyc.py`, `scoring.py` and `rules.py`, no automated test. Gap: nothing asserts that screeners never block or close a case.

Related: FR-004, FR-006, FR-007, FR-009, FR-011.

## Change Notes
- v1.1: Phase 4 (proposed) clauses extended with FR-011: `consistency_warning` never overrides the recommendation; FR-011 added to Related.
