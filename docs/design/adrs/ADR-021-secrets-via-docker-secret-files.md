---
id: "ADR-021"
title: "Secrets via Docker secret files with env fallback and sanitized errors"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-006"]
focus_track: "security"
evidence: "inferred"
---

# ADR-021: Secrets via Docker secret files with env fallback and sanitized errors

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
The investigator needs a DB password and, in anthropic mode, a model API key. Existing config is hard-coded demo values (ADR-013). Real keys must never be committed, logged or audited (IA-5, ASVS V14). Design decision D5; B8 in ARCH-001. `.gitignore` currently lacks `secrets/`, `.jetro/`, `.claude-flow/`.

## Decision
We will use Docker/Compose secret files:
- DB password: one file, `/run/secrets/investigator_db_password`. `migrate` reads it (psql `\set` from `cat`, `set_config(..., true)` inside the DO block, `ALTER ROLE ... PASSWORD` each start; see ADR-018). The investigator builds its DSN from the same file via `INVESTIGATOR_DB_PASSWORD_FILE` and `INVESTIGATOR_DB_HOST`, with no fallback; `INVESTIGATOR_DSN` and `INVESTIGATOR_DSN_FILE` are removed.
- API key: `ANTHROPIC_API_KEY_FILE` (default `/run/secrets/anthropic_api_key`); env `ANTHROPIC_API_KEY` only as a local-development fallback. The key is read only when `LLM_MODE=anthropic`, never logged or stored, and provider exceptions are sanitized to exception type plus status.
- Compose secret source paths default to committed synthetic demo files under `secrets/demo/`, so CI works without real secrets.
- `.gitignore` gains `secrets/*`, `!secrets/demo/`, `.jetro/` and `.claude-flow/`.
- FR-010.3 and NFR-006 were amended at Design to match this decision.

## Alternatives rejected
- Environment variables only: leak via process listings, `docker inspect` and crash dumps.
- Vault/KMS: deferred; disproportionate for a synthetic-data demo.

## Consequences
Positive: secrets stay out of images, repo and logs; stub mode requires none (NFR-006, NFR-007). Negative (cost accepted): extra compose wiring (secrets section, file mounts); two config paths to test; committed demo secret files must stay synthetic; demo passwords for existing services remain (ADR-013, ADR-015). Residual risk: psql error context and server logs can echo the statement containing the password.
