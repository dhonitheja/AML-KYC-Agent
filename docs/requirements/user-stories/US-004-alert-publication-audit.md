---
id: "US-004"
title: "Alerts published and every decision audited"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "auditor"
implements_fr: ["FR-004"]
implements_nfr: ["NFR-004"]
test_files: ["latency.py"]
epic: "audit"
---

# US-004: Alerts published and every decision audited

## Story
As an **auditor**, I want **each score and alert recorded in the audit table and published to the alerts topic**, so that **I can reconstruct every decision**.

## Acceptance Criteria
- [ ] AC-1: Given a scored transaction, when scoring completes, then one scored.v1 audit row exists, plus one alerted.v1 row if score >= 60.
- [ ] AC-2: Given an alert, when it is published after DB commit, then the message carries transaction_id, case_id, run_id, version, score, alert and rules with evidence.
- [ ] AC-3: Given a replayed transaction, when scoring reruns, then the prior scored.v1 result is reused and no second row is added.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | none yet (gap) | one scored.v1 audit row exists, plus one alerted.v1 row if score >= 60 |
| AC-2 | latency.py:30 | the alert carries rapid_pass_through rule evidence (partial; other message fields are a gap) |
| AC-3 | none yet (gap) | the prior scored.v1 result is reused and no second row is added |
