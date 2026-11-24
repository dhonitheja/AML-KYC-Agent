---
id: "ADR-016"
title: "Recommend-only posture"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-005"]
evidence: "documented"
---

# ADR-016: Recommend-only posture

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Screening records results and never blocks or closes anything (kyc.py:51-90 return or audit only; `requires_review` is a flag, kyc.py:78). The scorer only publishes alerts (scoring.py:53). The `aml_worker` role has no INSERT on `cases` (sql/001-foundations.sql:22). NFR-005 requires automated components to recommend only. R-16.

## Decision
We will make every automated component advisory: it records findings and publishes alerts; humans decide dispositions, and no component changes case status, blocks transactions or files reports.

## Consequences
Positive: human-in-the-loop alignment (FFIEC, SR 11-7) and a small blast radius for model error. Negative: no analyst disposition recording (RR-4); the posture is enforced by grants and code review, with no test (NFR-005 gap).
