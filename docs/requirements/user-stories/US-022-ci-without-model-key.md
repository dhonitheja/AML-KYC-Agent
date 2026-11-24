---
id: "US-022"
title: "CI runs with no model key"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-010"]
implements_nfr: ["NFR-006", "NFR-007"]
test_files: ["tests/conftest.py", "tests/test_investigator.py", "tests/test_llm.py"]
epic: "model-provider"
---

# US-022: CI runs with no model key

## Story
As a **platform engineer**, I want **the deterministic stub used when no credentials exist**, so that **CI and local tests are reproducible and need no secrets**.

## Acceptance Criteria
- [x] AC-1: Given no model API key in the environment, when the stack and tests run, then the deterministic stub produces the same narrative on every run.
- [x] AC-2: Given the stub, when it is used, then model_version identifies it as a stub.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_llm.py (test_stub_is_deterministic); tests/conftest.py guard; CI runs with no key | the deterministic stub produces the same narrative on every run |
| AC-2 | tests/test_investigator.py (test_stack_drafted_row_stub) | model_version identifies it as a stub |
