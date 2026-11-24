---
id: "ADR-018"
title: "Dedicated aml_investigator role, investigator_audit view and insert guard trigger"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-005", "NFR-006"]
focus_track: "security"
evidence: "inferred"
---

# ADR-018: Dedicated aml_investigator role, investigator_audit view and insert guard trigger

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
The investigator needs to read transactions and prior scoring and screening evidence, and write its own outcome rows. `audit` also contains onboarding rows (`kyc.reviewed.v1`, `onboarding.screened.v1`, api.py:46-48) with applicant names, which the model must never see. The existing role `aml_worker` is shared by three services with a self-asserted `actor` (RR-13). Design decision D2 (CS-010 items 2-6).

## Decision
We will create a separate login role `aml_investigator` (no superuser/createdb/createrole/bypassrls) in sql/004:
- SELECT on `transactions` and on view `investigator_audit` only (columns event_id, recorded_at, actor, action, case_id, transaction_id, inputs, model_version, prompt_version, filtered to actions `scored.v1`, `payment.screened.v1`, `alerted.v1` (W2: the investigator needs it to confirm an alert row exists, ADR-023), `investigation.drafted.v1`, `investigation.skipped.v1`); NO SELECT on `audit`, `kyc_applications`, `screened_counterparties`, `cases`.
- INSERT on `audit` plus USAGE on `audit_event_id_seq`.
- A two-way BEFORE INSERT trigger on `audit`: (a) `aml_investigator` may write only actor `investigator-v1` with action `investigation.drafted.v1` or `investigation.skipped.v1`; (b) any row with an `investigation.*` action or actor `investigator-v1` requires `current_user = 'aml_investigator'`. Rule (b) stops `aml_worker` from forging narratives or squatting `alert_key` slots (ADR-023).
- Because the role cannot SELECT `audit`, its INSERTs never use `RETURNING`; outcome is read from `cursor.rowcount`, with `ON CONFLICT DO NOTHING` without a conflict target.
- The role password comes from one secret file, `/run/secrets/investigator_db_password` (ADR-021). `migrate` reads it with psql `\set` from `cat`, passes it into the DO block via `set_config(..., true)` (transaction-local), creates the role, and runs `ALTER ROLE ... PASSWORD` on every start to stay in sync with the file.
- The investigator builds its DSN from the same file (`INVESTIGATOR_DB_PASSWORD_FILE`, host from `INVESTIGATOR_DB_HOST`) and fails fast if the file is missing; there is no fallback to the `aml_worker` DSN. `INVESTIGATOR_DSN` and `INVESTIGATOR_DSN_FILE` are removed.
- Migration split (amends ADR-014): initdb mounts only 001; `migrate` runs 002-004, so 004 (which needs the secret) never runs at initdb.

## Alternatives rejected
- Reuse `aml_worker`: would give the model-facing service read access to KYC PII and let it forge any actor/action.
- Row-level security on `audit`: more moving parts and policy interactions with owner and superuser than a view plus grants, and still exposes the table to the role.

## Consequences
Positive: PII exclusion and write pinning are enforced by the database, not application code (AC-6, GLBA, LLM02, LLM06). Negative (cost accepted): an extra role, password and migration complexity (the password is handed to the migrate step via psql `\set` and `set_config`); `RETURNING` cannot be used; the view is owner-controlled, so a superuser can redefine it (RR-5, RR-12). Existing services still share `aml_worker` (RR-13). Residual risk: psql error context and Postgres server logs can echo the statement containing the password.
