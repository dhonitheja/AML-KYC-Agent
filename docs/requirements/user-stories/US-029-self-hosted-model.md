---
id: "US-029"
title: "Draft narratives with a self-hosted model"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-23"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-010"]
implements_nfr: ["NFR-008"]
test_files: ["tests/egress_check.py", "tests/test_investigator.py", "tests/test_llm.py"]
epic: "model-provider"
---

# US-029: Draft narratives with a self-hosted model

## Story
As a **platform engineer**, I want **the investigation agent to use a model server running inside our deployment**, so that **analysts get AI-drafted narratives while customer data never leaves our infrastructure**.

## Acceptance Criteria
- [x] AC-1: Given LLM_MODE=local with LOCAL_LLM_URL and LLM_MODEL set, when an alert is processed, then a drafted row records model_version equal to LLM_MODEL and passes the same grounding checks as other modes (FR-010.5 AC-3).
- [x] AC-2: Given LLM_MODE=local with LOCAL_LLM_URL or LLM_MODEL unset, when the investigator starts, then it fails with a clear error (FR-010.5 AC-1, AC-2).
- [ ] AC-3: Given local mode, when the investigator tries to reach a host outside the deployment, then the connection fails, while the in-deployment model server is reachable (NFR-008 AC-6).
- [x] AC-4: Given the model server is down, when an alert is processed, then it is recorded as skipped with reason model_failure and the consumer moves on (FR-010.5 AC-4).

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_investigator.py (test_stack_local_mode_drafted, loopback fake server); real Ollama only in the opt-in `local-model` job | local-mode drafted row records LLM_MODEL |
| AC-2 | tests/test_investigator.py (test_local_without_url_exits, test_local_without_model_exits) | missing local config fails startup |
| AC-3 | opt-in `local-model` job only (egress_check --allow llm:11434); network half runs every push via NFR-008 AC-1. UNVERIFIED on push | no external route; model server reachable |
| AC-4 | tests/test_investigator.py (test_stack_main_local_unreachable_commits_after_row); tests/test_llm.py (test_local_refused_port_exhausts) | model server down gives model_failure skip |
