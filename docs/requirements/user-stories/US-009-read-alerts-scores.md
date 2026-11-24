---
id: "US-009"
title: "Query alerts and scores via the read API"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-008"]
implements_nfr: ["NFR-003"]
test_files: []
epic: "api"
---

# US-009: Query alerts and scores via the read API

## Story
As an **AML compliance analyst**, I want **GET /alerts and GET /scores/{id}**, so that **I can see what was flagged and why**.

## Acceptance Criteria
- [ ] AC-1: Given an alert exists for AML-1042, when GET /alerts is called, then the list includes AML-1042.
- [ ] AC-2: Given a scored transaction id, when GET /scores/{id} is called, then the score and rule evidence are returned from the audit table.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | .github/workflows/ci.yml:13 | the list includes AML-1042 |
| AC-2 | none yet (gap) (/scores 404 and score/evidence response untested) | the score and rule evidence are returned from the audit table |
