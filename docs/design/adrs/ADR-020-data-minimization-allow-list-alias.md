---
id: "ADR-020"
title: "Data minimization allow-list, SUBJECT_ACCOUNT alias and stored payload hash"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004", "NFR-006"]
focus_track: "security"
evidence: "inferred"
---

# ADR-020: Data minimization allow-list, SUBJECT_ACCOUNT alias and stored payload hash

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
Data leaving the system to a third-party model (B12) should be the minimum needed (GLBA Safeguards, OWASP LLM02). The alert message carries no account (B10); the account is re-read from the DB. We also need to prove later exactly what was sent (NFR-004). Design decision D4.

## Decision
We will build the evidence payload from a deny-by-default field allow-list, replace the real account with the alias `SUBJECT_ACCOUNT`, include no KYC data, and store the exact payload sent plus its SHA-256 in `audit.inputs` of the investigation row.

## Alternatives rejected
- Send full rows: exposes unnecessary fields and any future added columns automatically.
- HMAC pseudonyms for accounts: needs key management and gives little extra protection for a per-alert alias, since the evidence has no cross-alert linkage purpose.

## Consequences
Positive: new columns do not leak by default; reproducibility and tamper evidence for the model input. Negative (cost accepted): the model sees less context (no real account identity, no KYC), which may reduce narrative quality; storing payloads grows audit rows; the stored payload itself becomes retained data (ADR-025).
