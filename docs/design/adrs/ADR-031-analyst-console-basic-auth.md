---
id: "ADR-031"
title: "Analyst console with HTTP Basic auth from a secret file"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-24"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-005"]
evidence: "documented"
---

# ADR-031: Analyst console with HTTP Basic auth from a secret file

## Status
Accepted by the user at the Phase 5 sign-off (2026-11-24).

## Context
RR-4 (no analyst disposition recording) and ADR-012 (real use needs authN/Z). Decisions must name a person, so the console needs identity. The API is still loopback only and data is synthetic (ADR-015). Drafts are model output and untrusted (ADR-019).

## Decision
We will add console routes to `api.py` protected by HTTP Basic against `name:password` lines in the Compose secret `analysts` (`ANALYSTS_SECRET`, default `secrets/demo/analysts`), compared with `hmac.compare_digest`. The analyst name comes only from authentication and is written as `actor=analyst:<name>`. `POST` requires `application/json`, which a cross-site form cannot send without a CORS preflight the API never grants. The page renders every API value with `textContent`. A partial unique index (`sql/005-console.sql`) allows one `analyst.decided.v1` row per transaction. The existing `/alerts`, `/scores` and `/onboarding` routes stay unauthenticated (ADR-012).

## Consequences
Positive: one file of credentials, no new dependency, a native browser sign-in prompt, accountable append-only decisions. Negative: plaintext passwords in a secret file, no lockout, no roles, no sign-out; Basic credentials travel unencrypted, which is acceptable only on loopback. Every service connects as `aml_worker`, so the database cannot prove an `analyst:` row came from the console (residual risk). A decision cannot be amended. Before non-local use, replace Basic auth with an identity provider (OIDC) behind TLS and give the API its own DB role.
