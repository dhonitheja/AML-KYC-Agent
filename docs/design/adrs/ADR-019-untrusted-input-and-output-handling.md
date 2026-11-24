---
id: "ADR-019"
title: "Untrusted-input and output handling for the model call"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-005", "NFR-006"]
focus_track: "security"
evidence: "inferred"
---

# ADR-019: Untrusted-input and output handling for the model call

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
Evidence sent to the model includes attacker-influenced text, notably `counterparty` names (prompt injection, OWASP LLM01), and the model's output is stored and shown to analysts (LLM05). The model must have no way to act (LLM06, NFR-005). Design decision D3; B12, B13 in ARCH-001.

## Decision
We will:
- Send evidence as one JSON object inside a delimited `<evidence>` block, with a system prompt stating the content is untrusted data, never instructions.
- Strip control characters and cap strings at 256 characters; cap history at 50 transactions / 30 days. Rule evidence with more than 50 ids per rule is truncated to 50 ids for the model and marked `evidence_truncated`; it is never rejected (W1).
- Provide no tools or function calling, no streaming.
- Require output matching a strict pydantic model (`extra=forbid`): `summary` (max 2,000 chars), `recommendation` enum, `cited_transaction_ids`. ADR-027 extends this strict model with a `findings` field (still `extra=forbid`), so the two ADRs do not conflict.
- Require every cited id to be a subset of the evidence ids.
- On invalid output, retry (bounded, ADR-022), then record `investigation.skipped.v1` with reason `model_failure`. Grounding of claims is checked separately (ADR-027).
- Store the summary as inert text; never execute it or render it as HTML.

## Alternatives rejected
- Free-text output: cannot be validated, and citations could be invented.
- Tool use / function calling: gives injected text a path to cause actions, contradicting NFR-005.

## Consequences
Positive: worst-case outcome of a successful injection is a misleading summary, which a human analyst weighs; citations are checkable. Negative (cost accepted): invalid drafts cost retries and ultimately become permanent skips (RR-10); long histories are truncated so the model sees less; delimiters reduce but do not eliminate injection risk. Serves LLM01, LLM05, LLM06, LLM10.
