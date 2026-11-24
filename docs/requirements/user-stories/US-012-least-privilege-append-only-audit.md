---
id: "US-012"
title: "Append-only audit with least-privilege access"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "auditor"
implements_fr: ["FR-004"]
implements_nfr: ["NFR-003", "NFR-004"]
test_files: []
epic: "audit"
---

# US-012: Append-only audit with least-privilege access

## Story
As an **auditor**, I want **the application role to only SELECT and INSERT audit rows**, so that **audit history cannot be altered by the application**.

## Acceptance Criteria
- [ ] AC-1: Given the aml_worker role, when it attempts UPDATE or DELETE on audit, then the database denies it.
- [ ] AC-2: Given aml_worker, when it attempts INSERT into cases, then the database denies it.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | none yet (planned) | the database denies it |
| AC-2 | none yet (planned) | the database denies it |
