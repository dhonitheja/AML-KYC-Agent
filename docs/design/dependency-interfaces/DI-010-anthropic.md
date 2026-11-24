---
id: "DI-010"
title: "Anthropic API and Python SDK (PROPOSED, Phase 4)"
type: "dependency-interface"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "anthropic"
version_constraint: "== 1.17.0 (requirements.txt); `>=`/`~=` ranges forbidden"
satisfies_fr: ["FR-010", "FR-009"]
satisfies_nfr: ["NFR-005", "NFR-006", "NFR-007"]
constrained_by_adrs: ["ADR-021", "ADR-022"]
---

# DI-010: anthropic

## Purpose
Real-mode narrative drafting for CS-008 through CS-009 `AnthropicLLM`. Opt-in via `LLM_MODE=anthropic`; default is the offline stub, so CI needs no key or network (FR-010.2, NFR-007). `anthropic==1.17.0` is the latest 1.x at implementation (2026-11-24); 2.x is deliberately not adopted and needs a separate reviewed change (ADR-022). It is pinned with `==` and bumped only by a reviewed change, because a new SDK version changes the egress client.

## Classes/Methods/Functions Used
- `anthropic.Anthropic(api_key=<key>, max_retries=0, timeout=<LLM_TIMEOUT_SECONDS>)`, one client per process, created only in anthropic mode (lazy import).
- `client.messages.create(model=<LLM_MODEL, default claude-opus-5-5>, max_tokens=16000, output_config={"effort": "low"}, system=<system>, messages=[{"role":"user","content":<user>}])`; no `tools`, no streaming, no files.
- Response use: text blocks joined; `response.model` stored as `audit.model_version`.
- Exceptions inspected by class and `status_code` only: `APITimeoutError`, `APIConnectionError`, `RateLimitError` (429), `InternalServerError`/5xx (retried); `BadRequestError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `UnprocessableEntityError` (non-retryable).

## Data Exchanged
Sent (egress over HTTPS to `api.anthropic.com`, TLS verified by the SDK's httpx default; no proxy or base-URL override accepted from env except as an explicit reviewed change): the system prompt and ONE user message holding the allow-listed, minimized evidence in `<evidence>` tags, with the account pseudonymized to `SUBJECT_ACCOUNT`, strings capped at 256 chars and stripped of control characters (CS-008 `build_evidence`). Fields: transaction id, counterparty, amount_cents, direction, channel, occurred_at, up to 50 history entries, rule names/points/evidence ids, screening hits (names, scores, dispositions, snapshot hash). Never sent: account id, run_id, onboarding data, DSN, key, audit history, free-text case fields.
Received: one JSON text, validated by strict pydantic with citation-subset check; untrusted until validated; prompt-injected instructions inside evidence cannot trigger actions because no tools are granted and the output is only stored if schema-valid.

## Failure Modes and Timeouts
Per-call timeout `LLM_TIMEOUT_SECONDS` (default 30); SDK retries off so total attempts = `LLM_MAX_ATTEMPTS` (default 3) with exponential backoff and jitter (CS-009). Exhausted retries record `investigation.skipped.v1` reason `model_failure`; no narrative is fabricated; the consumer moves on. Outage, rate limiting or key revocation therefore degrade to skipped rows, not crash loops. 401/403 are non-retryable and visible as `model_failure` rows with sanitized error class.

## Security Notes
- Key from `ANTHROPIC_API_KEY_FILE` (default `/run/secrets/anthropic_api_key`, Compose secret `anthropic_api_key`, source `${ANTHROPIC_API_KEY_SECRET:-./secrets/demo/anthropic_api_key}`; the committed demo file is empty), with `ANTHROPIC_API_KEY` env only as a dev fallback, read only when `LLM_MODE=anthropic`; required at startup only in anthropic mode; never in the repo, image, audit rows, logs, prompts or exception text.
- Errors are sanitized to type plus status code and are never chained (SDK exceptions can carry request headers/body).
- Logs carry `transaction_id`/`alert_key`, outcome, attempts, latency only.
- The container runs as non-root uid 10001 (`USER app` in the Dockerfile, applies to all services); the secret file must be readable by that uid and nothing else.
- Egress should be limited to `api.anthropic.com:443` by network policy; the investigator is the only service with this egress and the key.
- Data minimization and pseudonymization are the privacy control (NFR-006); confirm provider data-retention terms before any non-synthetic use (synthetic data only today, NFR-006 / US-014).
- Model output is advisory only (NFR-005).
- Pinned model id is recorded per row for reproducibility; output is not deterministic (current models accept no `temperature`), hence stored `prompt_sha256`, `evidence_sha256` and the raw validated draft.

## Why This Dependency
Official SDK gives typed errors with status codes, timeouts and TLS handling. Replacing it (another provider, raw httpx) means implementing the CS-009 `LLM` protocol (`complete(system, user) -> (text, model_id)`) and mapping that provider's timeout/429/5xx errors into the same retry classes; CS-008, the audit schema and the validation layer stay unchanged, which is the point of the protocol (FR-010).

## Change notes
- v1.1 (2026-11-24, Requirements Sync, PLAN-002): recorded the pinned release `anthropic==1.17.0` (latest 1.x at implementation); 2.x not adopted.
