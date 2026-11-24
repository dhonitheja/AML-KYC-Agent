---
id: "ADR-022"
title: "Anthropic SDK, exact pin, own retry, deterministic parameters and recorded versions"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004", "NFR-005", "NFR-006", "NFR-007"]
focus_track: "ai"
evidence: "inferred"
---

# ADR-022: Anthropic SDK, exact pin, own retry, deterministic parameters and recorded versions

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
FR-010 requires a switchable model provider with a deterministic offline stub as default (CI needs no key, NFR-007) and recorded model/prompt versions for reproducibility (NFR-004, SR 11-7). Retries must be bounded so cost and `max.poll.interval.ms` sizing are exact (LLM10; ADR-017). Design decision D6; CS-009, DI-010.

## Decision
We will call the Anthropic Messages API through the official `anthropic` SDK pinned to an exact version in requirements.txt, with `max_retries=0` and our own bounded retry loop (timeouts, connection errors, 429, 5xx, validation failures; exponential backoff with jitter; `LLM_MAX_ATTEMPTS`), `max_tokens=16000`, `output_config={"effort": "low"}`, no `temperature`, no tools, no fallbacks. Each row records the model id returned by the API, `prompt_version`, and `prompt_sha256`. `LLM_MODE` defaults to `stub` (no network).

## Alternatives rejected
- Raw HTTP: re-implements auth, error typing and API drift handling.
- SDK built-in retries: hidden attempts break the exact time and cost bound.

## Consequences
Positive: exact worst-case time bound; fixed request parameters; CI runs without a key. Negative (cost accepted): a new dependency to monitor and re-pin; output is not deterministic, so evidence payload and draft are stored rather than regenerated; default `LLM_MODEL` is a moving alias (RR-8); third-party data processing is acceptable only because data is synthetic (ADR-015).


## Amendment 2026-11-23 (user decision before Develop)

Corrected to current Claude API behaviour: `temperature` is removed, because current models reject any sampling parameter with a 400. Thinking is always on and cannot be disabled, and thinking tokens count toward `max_tokens`, so `max_tokens` is 16000 with `output_config={"effort": "low"}` (a short extraction task). A response with `stop_reason` `refusal` or `max_tokens` is a non-retryable `model_failure`; no server-side `fallbacks` parameter is sent, so only the configured, recorded model ever writes a narrative (SR 11-7 model inventory). Default `LLM_MODEL` is `claude-opus-5-5`, the user's choice. The `anthropic` 1.x SDK (built on `httpx2`) is pinned to the exact version that `pip index versions anthropic` reports at implementation time; no version number is guessed.

## Amendment (accepted 2026-11-24, see ADR-030)
Anthropic mode is additionally gated on `DATA_CLASSIFICATION=synthetic`, and the compose default for `LLM_MODEL` is removed (the default moves into code). The decision above is otherwise unchanged.
