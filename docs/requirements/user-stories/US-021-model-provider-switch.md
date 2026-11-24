---
id: "US-021"
title: "Switch model provider by configuration"
type: "user-story"
priority: "P2"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-010"]
implements_nfr: ["NFR-006", "NFR-008"]
test_files: ["tests/test_investigator.py"]
epic: "model-provider"
---

# US-021: Switch model provider by configuration

## Story
As a **platform engineer**, I want **to select the model provider through configuration**, so that **I can move between the stub, a self-hosted model and (for synthetic data only) a hosted model without code changes**.

## Acceptance Criteria
- [x] AC-1: Given a provider is configured (with credentials for anthropic, or LOCAL_LLM_URL for local), when the agent runs, then that provider is used and audit.model_version records the model id (LLM_MODEL; the stub records "stub-v1"), not the provider, with prompt_version e.g. "investigation-prompt-v2".
- [x] AC-2: Given an unsupported LLM_MODE value (supported: stub, the default; local; or anthropic, which also requires DATA_CLASSIFICATION=synthetic; LLM_MODEL defaults to "claude-opus-5-5" in anthropic mode and is required in local mode; stub records model_version "stub-v1"), when the service starts, then it fails with a clear error.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_make_llm_and_params_per_mode, test_stack_drafted_row_stub, test_stack_local_mode_drafted) | audit.model_version records the model id and prompt_version |
| AC-2 | tests/test_investigator.py (test_bogus_mode_exits, test_anthropic_without_classification_exits_before_any_read, test_local_without_url_exits) | it fails with a clear error |
