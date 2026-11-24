---
id: "DI-011"
title: "Local model server HTTP API, Ollama (PROPOSED, Phase 4)"
type: "dependency-interface"
status: "approved"
version: "1.1"
created: "2026-11-23"
author: "component-spec-author-agent"
package: "ollama (container image; no Python package)"
version_constraint: "image pinned by digest at Develop (ADR-029); no Python dependency added (stdlib urllib client)"
satisfies_fr: ["FR-010", "FR-009"]
satisfies_nfr: ["NFR-005", "NFR-006", "NFR-008"]
constrained_by_adrs: ["ADR-019", "ADR-020", "ADR-022", "ADR-028", "ADR-029"]
---

# DI-011: local model server (Ollama HTTP API)

## Purpose
In-deployment model backend for `LLM_MODE=local` (FR-010.5) through CS-009 `LocalLLM`. It lets the investigator draft narratives without evidence leaving the Compose deployment (NFR-008). A new Compose service named `llm` (ARCH-001 section 1a, ADR-029), image pinned, on the `internal` network only.

## Classes/Methods/Functions Used
No SDK. One endpoint: `POST {LOCAL_LLM_URL}/api/chat` with `{"model": <LLM_MODEL>, "stream": false, "format": "json", "messages": [system, user], "options": {"temperature": 0, "num_predict": 4096}}` (`num_predict` caps output tokens, LLM10; 4096 exceeds the largest schema-valid `Draft`, so a `done_reason` of `length` means a runaway or non-conforming answer and is non-retryable). The client is stdlib `urllib.request` plus `json` in `llm.py`. Response fields used: `message.content` (text), `done_reason` (`length` is non-retryable), optional `error`. Any other server exposing the same shape (or a thin adapter) is acceptable; `LOCAL_LLM_URL` is the only coupling.

## Data Exchanged
Sent (plain HTTP, internal network): the same system prompt and single user message with allow-listed, pseudonymized evidence as in DI-010. Received: one JSON text, untrusted until `validate_draft` and `check_grounding` pass. No tools, no API key, no auth header.

## Failure Modes and Timeouts
Per-call timeout `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ATTEMPTS` attempts, backoff per CS-009. Connection refused, timeout, 429 and 5xx are retryable; other 4xx are non-retryable (404 = model not present). Exhaustion gives `skipped(model_failure)` (FR-010.5 AC-4). Errors are reduced to class and status.

## Security Notes
- Internal network only; no host port published (NFR-008.1/.2). Weights are baked into the image or a local volume; the server must not pull at runtime (FR-010.5 AC-6). Server-side logging must not record prompts, since evidence is customer data; verify at Develop.
- No TLS inside the deployment: accepted, traffic stays on the internal Docker network. The URL host is not validated; network isolation is the control (FR-010.5 AC-5).
- Small local models are less reliable and non-deterministic; grounding failures are expected more often and end in `skipped`, never a fabricated draft (FR-011).
- Container user: the upstream Ollama image runs as root by default. Develop SHOULD set a non-root `user:` in Compose (with a writable model volume owned by that uid) if the pinned image supports it; if not, the service runs as root and this is recorded as a residual risk for the architecture author to add (ARCH-001 RR (llm container user)). It is internal-only with no host port, no secrets and no database access, which limits the blast radius.
- The client builds its opener with `ProxyHandler({})` and no redirect handling (CS-009), so proxy env vars and 3xx responses cannot reroute evidence.
- Image pull happens at deploy time under NFR-008.3(d); the image is the only supply-chain input.

## Why This Dependency
Needed so real-model drafting is possible on customer data. Replacing it (vLLM, llama.cpp server) means a new request/response mapping in `LocalLLM` only; the `LLM` protocol, CS-008, validation and audit schema stay unchanged. A stdlib client was chosen over adding httpx or requests to avoid a new dependency and a wider NFR-008 AC-5 network-import grep scope.

## Change notes
- v1.1 (2026-11-23, gate round 7): `num_predict` cap, container user residual risk, no-proxy/no-redirect client.
