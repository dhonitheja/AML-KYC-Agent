---
id: "US-015"
title: "Reproducible CI run on Docker Compose"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: []
implements_nfr: ["NFR-007"]
test_files: []
epic: "platform"
---

# US-015: Reproducible CI run on Docker Compose

## Story
As a **platform engineer**, I want **CI to run pytest, seed, latency, the AML-1042 check and the benchmark**, so that **every change is verified identically to local runs**.

## Acceptance Criteria
- [ ] AC-1: Given a clean checkout, when CI runs, then the steps run in order and all pass.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | .github/workflows/ci.yml | the steps run in order and all pass |
