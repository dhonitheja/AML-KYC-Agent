---
id: "ADR-024"
title: "Audit immutability triggers blocking UPDATE, DELETE and TRUNCATE"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-004"]
focus_track: "security"
evidence: "inferred"
---

# ADR-024: Audit immutability triggers blocking UPDATE, DELETE and TRUNCATE

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
ADR-003 makes audit append-only only through grants for `aml_worker`; the owner and superuser (which runs `migrate`, ADR-014) can still modify rows. 31 CFR 1010.430 and NIST AU-9 call for protecting audit records. Design decision D7; B14.

## Decision
We will add BEFORE UPDATE OR DELETE (row) and BEFORE TRUNCATE (statement) triggers on `audit` that raise an exception for every role including the owner. The functions are not SECURITY DEFINER and have a pinned `search_path`; triggers are created only if absent so the migration remains idempotent.

## Alternatives rejected
- Grants only: does not bind the owner or superuser.
- Hash chain: stronger tamper evidence but deferred (RR-5) as disproportionate for the demo.

## Consequences
Positive: accidental or buggy mutation by any role fails loudly. Negative (cost accepted): a superuser can still DROP or disable the triggers (RR-5), no tamper evidence after that; a DBA correction needs an explicit trigger disable, and test setup must never TRUNCATE `audit` (none currently do); no hash chain.
