---
id: "ADR-027"
title: "Hallucination and grounding controls for drafted narratives"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004", "NFR-005"]
focus_track: "ai"
evidence: "inferred"
---

# ADR-027: Hallucination and grounding controls for drafted narratives

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
FR-011 requires that a model-drafted narrative cannot state facts the evidence does not contain. ADR-019 validates only the output shape and that cited transaction ids are a subset of the evidence ids; it does not catch an invented amount, an invented counterparty name, a rule that never fired, or a sanctions claim with no screening hit. An analyst may over-trust a fluent but false narrative (OWASP LLM09, overreliance and misinformation). SR 11-7 expects ongoing validation and outcome analysis of model output. NFR-004 needs reproducible, checkable audit rows and NFR-005 needs the output to stay advisory. Retry and skip mechanics are in ADR-022 and ADR-023.

## Decision
We will add these controls to the investigator (CS-008, CS-009):
1. The model output carries claim-level findings (each claim with the evidence it relies on), not only a free-text summary.
2. Before any write, deterministic code-only grounding checks run: every amount matches an evidence amount; every counterparty name appears in the evidence; every named rule is a rule that fired; sanctions wording is allowed only when a screening hit exists in the evidence. No model is used in the checks.
3. A failed check counts as a failed attempt (ADR-022). After `LLM_MAX_ATTEMPTS`, the investigator records `investigation.skipped.v1` with reason `grounding_failure` (ADR-023).
4. A `consistency_warning` is added when `no_further_action_suggested` conflicts with a rule scoring at least 60 points or with a screening hit. It never overrides the model's recommendation.
5. Every drafted row carries the labels `ai_generated`, `requires_human_review` and a grounding label (result of the checks).
6. A versioned synthetic evaluation set of at least 8 scenarios is kept in the repo. The stub run must pass in CI. An opt-in real-model run reports grounding-failure rate, citation-violation rate and recommendation agreement to a local report, never to the production audit.
7. Pinned grounding rules:
   - Amounts: `$`-prefixed amounts are matched whole with `\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|[.,]\d)` and never truncated. The lookahead lets amounts followed by prose punctuation (comma, period, semicolon, parenthesis) match whole, while rejecting malformed groupings such as \"$1,00\", \"$1,0000\" and \"$1,000,0\"; it was verified against 15 cases listed in CS-008. Each is parsed to integer cents; the fractional part must be exactly 2 digits. Any `$`+digit occurrence not fully matched fails. Each amount must equal an evidence amount or the sum of the cited transactions. Amounts without `$` are not checked: an accepted residual (RR-21), because bare decimals cannot be told apart from screening scores; FR-011.2(a) was amended to say so. The prompt requires money written as `$X,XXX.XX`.
   - Counterparty names: quoted names only, checked with `watchlist.normalize`; unquoted names are an accepted residual.
   - Rules: snake_case rule tokens, with the recommendation values excluded.
   - Sanctions: word-boundary sanctions terms, allowed only with a screening hit, negations included.
8. Stub templates are pinned literal strings that pass all checks, verified by a unit test.
9. Classification: a schema-level `rule` field mismatch is `model_failure`; a rule named in the text is `grounding_failure`; the last failed attempt wins.

## Alternatives rejected
- A second-model "LLM-as-judge" verifier: costly, itself prone to hallucination, and not deterministic (breaks NFR-004 reproducibility).
- Free-text-only summary with citation checks only: misses false amounts and names, which is the failure mode that matters.
- Deterministic template narratives with no model: removes the analyst value that FR-009 exists to provide.

## Consequences
Positive: false amounts, names, rules and sanctions claims are blocked before they reach an analyst; labels make the draft status explicit on every row (LLM09, NFR-005); outcome analysis is repeatable and kept out of the production audit (SR 11-7). Negative (cost accepted): strict checks reject some valid but loosely worded narratives, so more retries and more permanent `grounding_failure` skips (same permanence as RR-10); the real model's `grounding_failure` rate is higher because negated sanctions wording (for example "no sanctions hit") is rejected; about 150 lines of validation code to build and maintain; amounts written without `$` are unchecked (RR-21); semantic misstatements that pass the checks are still possible and rely on human review.
