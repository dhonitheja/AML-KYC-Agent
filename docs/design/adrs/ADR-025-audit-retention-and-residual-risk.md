---
id: "ADR-025"
title: "Audit retention of at least five years, no deletion path, residual-risk register"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004", "NFR-006"]
evidence: "inferred"
---

# ADR-025: Audit retention of at least five years, no deletion path, residual-risk register

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
31 CFR 1010.430 requires retaining certain records for five years; privacy regimes may require deletion on request. The system keeps full decision inputs and, in Phase 4, model payloads and drafts in `audit`. Several security controls are intentionally deferred. Design decision D8; ARCH-001 sections 7 and 8 (register RR-1 onward).

## Decision
We will treat `audit` as retained for at least five years with no deletion path (consistent with ADR-024), and we will maintain the residual-risk register in ARCH-001 section 8 (RR-1 onward) as the authoritative list of deferred controls: internal TLS/SASL, at-rest encryption, API authN/Z and logging, analyst disposition recording, hash chain, PII tokenization, malformed-message handling, dated model id, token budget and circuit breaker, permanent `model_failure` skips, retention-versus-deletion conflict, shared `aml_worker` role, and duplicate model call window.

## Alternatives rejected
- A deletion or redaction path: contradicts append-only and retention; would require its own ADR, and in-scope BSA records take precedence.

## Consequences
Positive: clear, honest record of what is and is not protected. Negative (cost accepted): privacy-deletion requests conflict with retention (RR-11); storage grows monotonically; backup and retention operations are not built (volumes only); every deferral is conditional on synthetic data (ADR-015).
