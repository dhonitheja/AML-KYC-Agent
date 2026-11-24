---
id: "US-014"
title: "Synthetic data only"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: []
implements_nfr: ["NFR-006"]
test_files: []
epic: "compliance"
---

# US-014: Synthetic data only

## Story
As a **platform engineer**, I want **only synthetic data and local demo credentials used**, so that **no real personal data is exposed**.

## Acceptance Criteria
- [ ] AC-1: Given the repo, when grepping compose.yaml, .github/workflows/ci.yml and requirements.txt, then no model API key or real-data source is configured, CI runs with LLM_MODE unset (stub) (Phase 4, FR-010, built), and the seed command and watchlists/sample.xml are the only data sources.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | compose.yaml, .github/workflows/ci.yml, watchlists/sample.xml (manual grep check; no automated test) | no model key or real-data source configured; fixtures are the only data |
