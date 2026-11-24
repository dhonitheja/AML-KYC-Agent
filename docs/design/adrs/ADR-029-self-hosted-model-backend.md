---
id: "ADR-029"
title: "Self-hosted model backend (LLM_MODE=local)"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-23"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-008", "NFR-005", "NFR-006"]
focus_track: "security"
evidence: "documented"
---

# ADR-029: Self-hosted model backend (LLM_MODE=local)

## Status
Accepted by the user at the Design sign-off (2026-11-24, NFR-008 delta).

## Context
FR-010.5 needs a real-model drafting path whose evidence never leaves the deployment (NFR-008). ADR-022 covers only the Anthropic SDK path and the stub. Constraints: no new Python dependency if avoidable (NFR-007), no runtime network on `internal`, local models are less reliable than hosted ones, and the output is as untrusted as any model output (ADR-019, ADR-027). Sources: FR-010.5, CS-009 v1.1, DI-011, ARCH-001 B16.

## Decision
We will add a compose service `llm` running Ollama:
- Image pinned by digest (not a floating tag); weights baked into the image or provided from a local volume; no runtime pull (no `ollama pull` at start; `OLLAMA_NOPRUNE` only stops pruning, it does not stop pulls, so network isolation is the control); on `internal` only; no host port; no secrets, no DB access. Reached at `LOCAL_LLM_URL=http://llm:11434`.
- `LocalLLM` in `llm.py` uses stdlib `urllib.request` against `POST /api/chat` (DI-011): no new dependency, no redirects followed, plain HTTP on the internal network, no auth header. The URL host is not validated; network isolation (ADR-028) is the control, not a host allow-list (FR-010.5 AC-5).
- Same prompt, `validate_draft`, `check_grounding` and bounded retry as the other backends; an unreachable or failing server ends in `skipped(model_failure)`. The recorded `model_version` is `LLM_MODEL`.
- `llm.py` and `investigator.py` are the permitted network-using runtime modules besides the DB/Kafka/Redis clients and `watchlist.py`. NFR-008 AC-5's grep list (api.py, pipeline.py, scoring.py, kyc.py, rules.py) intentionally excludes them; their control is network placement (ADR-028).

## Consequences
Positive: customer evidence can be drafted by a model without leaving the deployment; no new dependency, so the AC-5 grep scope stays narrow; swapping the server (vLLM, llama.cpp) touches `LocalLLM` only.

Negative: no TLS or auth on the investigator-to-`llm` hop (RR-1; a same-network peer could call or impersonate `llm`, bounded by ADR-019/ADR-027 checks); a large image and a manual weights step; small local models fail grounding more often, producing more `skipped` rows; the server must not log prompts (verify in Develop); the image digest needs deliberate re-pinning. Develop (PLAN-001, to be revised for this delta) owns the weights-baking procedure and the actual image digest.

Rejected alternatives: (1) removing the AI feature entirely, which satisfies NFR-008 trivially but drops FR-009 value on real data; (2) hosted providers for customer data, which breaks NFR-008.3(a) and is allowed only for synthetic data (ADR-030). Cost accepted: operating a local model server and lower draft quality in exchange for data residency.

Relations: extends ADR-022 (adds a backend; Anthropic path unchanged). Satisfies NFR-008.1, NFR-008.4; supports NFR-005, NFR-006.
