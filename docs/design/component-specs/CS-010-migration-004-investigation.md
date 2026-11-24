---
id: "CS-010"
title: "Migration sql/004-investigation.sql (PROPOSED, Phase 4)"
type: "component-spec"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["sql/004-investigation.sql (new)", "sql/001-foundations.sql", "sql/002-scoring.sql", "sql/003-kyc.sql", "compose.yaml"]
satisfies_fr: ["FR-009", "FR-011"]
satisfies_nfr: ["NFR-002", "NFR-003", "NFR-004", "NFR-005", "NFR-006"]
constrained_by_adrs: ["ADR-014", "ADR-018", "ADR-023", "ADR-024", "ADR-025", "ADR-027"]
---

# CS-010: sql/004-investigation.sql

## Description
Adds the least-privilege investigator role, the read-only `investigator_audit` view, the two outcome indexes, and database-enforced immutability of `audit`. Idempotent; re-run by `migrate` on every startup. Compose changes: (a) postgres mounts ONLY `./sql/001-foundations.sql:/docker-entrypoint-initdb.d/001-foundations.sql:ro` (currently compose.yaml:24 mounts all of `./sql`, so initdb runs 001, 002, 003 and would run 004); (b) `migrate` runs 002, 003 and 004 on every start, fresh volume included (compose.yaml:39 extended with `-f /migrations/004-investigation.sql`); (c) `migrate` mounts compose secret `investigator_db_password` at `/run/secrets/investigator_db_password` and runs ``\set investigator_password `cat /run/secrets/investigator_db_password` `` in the same psql session before 004. Secret source `${INVESTIGATOR_DB_PASSWORD_SECRET:-./secrets/demo/investigator_db_password}` (committed demo file, synthetic value); psql strips the trailing newline of backtick command output; the investigator strips trailing whitespace from the same file (CS-008, W6), so both sides derive the same password. `.gitignore` has `secrets/*` and `!secrets/demo/`. `ON_ERROR_STOP=1` already set, so a missing secret fails the migration.

## Public Interface (DDL, in order, all inside BEGIN/COMMIT)
1. Password hand-off: `SELECT set_config('aml.investigator_password', :'investigator_password', true) IS NOT NULL AS password_set;` (the `set_config` result is suppressed behind `IS NOT NULL`, so psql never prints the password) (is_local=true, scoped to the 004 transaction; psql variable interpolation does not work inside dollar-quoted DO bodies, so the value is passed through a setting).
2. Role: `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aml_investigator') THEN EXECUTE format('CREATE ROLE aml_investigator LOGIN PASSWORD %L', current_setting('aml.investigator_password')); ELSE EXECUTE format('ALTER ROLE aml_investigator PASSWORD %L', current_setting('aml.investigator_password')); END IF; END $$;` The role is created if absent; if it already exists, ALTER ROLE ... PASSWORD runs every time so the password stays in sync with the secret file. Residual risk: psql echoes statement context on error and the server may log it, so the password can appear in migrate output or server logs on failure. The role is created without SUPERUSER, CREATEDB, CREATEROLE or BYPASSRLS (defaults).
3. View and grants: `CREATE OR REPLACE VIEW investigator_audit AS SELECT event_id, recorded_at, actor, action, case_id, transaction_id, inputs, model_version, prompt_version FROM audit WHERE action IN ('scored.v1','alerted.v1','payment.screened.v1','investigation.drafted.v1','investigation.skipped.v1');` `alerted.v1` is added (W2) so the investigator can confirm scoring really alerted the transaction (written with `scored.v1`, scoring.py:45; unique per transaction by `audit_score_once`, sql/002-scoring.sql:4). It carries only the scored payload, no applicant data. Owned by the migrating superuser (postgres); default (non-security_invoker) semantics, so reads run with the owner's rights and the investigator needs no privilege on `audit`. `GRANT SELECT ON transactions, investigator_audit TO aml_investigator; GRANT INSERT ON audit TO aml_investigator; GRANT USAGE ON SEQUENCE audit_event_id_seq TO aml_investigator;` NO SELECT on `audit` itself (it holds `onboarding.screened.v1` and `kyc.reviewed.v1` rows with applicant names). No grant on `cases`, `kyc_applications`, `screened_counterparties`, no UPDATE/DELETE/TRUNCATE.
4. Indexes:
   - `CREATE UNIQUE INDEX IF NOT EXISTS audit_investigation_drafted_once ON audit(transaction_id) WHERE action='investigation.drafted.v1';`
   - `CREATE UNIQUE INDEX IF NOT EXISTS audit_investigation_alert_once ON audit((inputs->>'alert_key')) WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1');` One index across both actions makes drafted and skipped mutually exclusive per alert at the DB level; drafted rows carry `alert_key = transaction_id`.
5. Functions: `CREATE OR REPLACE FUNCTION audit_investigator_guard() RETURNS trigger` (BEFORE INSERT): `IF current_user='aml_investigator' THEN IF NEW.actor='investigator-v1' AND NEW.action IN ('investigation.drafted.v1','investigation.skipped.v1') THEN RETURN NEW; END IF; RAISE EXCEPTION ...; ELSIF NEW.action LIKE 'investigation.%' OR NEW.actor='investigator-v1' THEN RAISE EXCEPTION ...; END IF; RETURN NEW;`. The guard applies in both directions: the investigator role may write only investigator-v1 drafted/skipped rows, and every investigation.* action or investigator-v1 actor requires `current_user='aml_investigator'`, so `aml_worker` cannot forge narratives or squat `alert_key` slots; any other combination raises. `CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger`: `RAISE EXCEPTION 'audit is append-only'`. Neither is SECURITY DEFINER: both run as the invoker (so `current_user` is the real session role) and must not need any privilege beyond what the invoker already has (they read only `NEW` and `current_user`, no table access); `SET search_path = pg_catalog, public` pinned on both.
6. Triggers, each created only if absent (guard by `pg_trigger` lookup in a DO block): `audit_investigator_guard_ins BEFORE INSERT ON audit FOR EACH ROW`; `audit_no_update_delete BEFORE UPDATE OR DELETE ON audit FOR EACH ROW`; `audit_no_truncate BEFORE TRUNCATE ON audit FOR EACH STATEMENT`. The immutability triggers raise for ALL roles including the table owner.

## Internal Data Structures
No new tables. Uses existing `audit(actor, action, case_id, transaction_id, inputs, model_version, prompt_version)`; `alert_key` lives in `inputs` JSON. New drafted-row `inputs` keys (`ai_generated`, `requires_human_review`, `grounding`, `consistency_warning`, `consistency_reason`, `evidence_truncated`, `evidence_original_counts`) and new skip reasons (`not_alerted`, `grounding_failure` with `failed_checks`) are JSON-only: no DDL, indexes unchanged. `not_alerted` and `unknown_transaction` use `alert_key="alerts:<partition>:<offset>"`, so a forged message cannot occupy a real transaction's `audit_investigation_alert_once` slot.

## Key Algorithms
Idempotency: `IF NOT EXISTS` role check, `CREATE INDEX IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`, trigger existence check. Running the migration twice succeeds (FR-009.5 AC-2).

## Component Interactions
Consumed by CS-008 (role, indexes, guard). Must not break existing writers: `aml_worker` only INSERTs (CS-001/002/004/006), so the immutability triggers do not affect it. Caveat: initdb and tests must not TRUNCATE/UPDATE `audit` (verified absent in tests/ and *.py). A superuser or table owner can still DROP TRIGGER; mitigate operationally by keeping the application roles non-owners and non-superuser (ownership/DDL separation is out of scope for the demo).

## Invariants
- `aml_investigator` can read `transactions` and the `investigator_audit` view (never raw `audit`) and append only investigation rows as actor `investigator-v1`.
- Investigator INSERTs into `audit` must NOT use `RETURNING` (needs SELECT) and use bare `ON CONFLICT DO NOTHING` with no conflict target, which needs no read privilege and fires on either partial unique index (`audit_investigation_drafted_once`, `audit_investigation_alert_once`). Outcome is read from `cursor.rowcount` (1 inserted, 0 conflict).
- No role can UPDATE, DELETE or TRUNCATE `audit` through SQL once the triggers exist (NFR-003, NFR-004).
- At most one drafted row per transaction; at most one drafted-or-skipped row per `alert_key`.
- The password lives in one secret file (`investigator_db_password`), is read by migrate (`\set` before 004) and by the investigator (`INVESTIGATOR_DB_PASSWORD_FILE`); nothing beyond the synthetic demo file is committed.

## Traceability
FR-009.5 (indexes, idempotent migration, role SELECT/INSERT only), FR-009.6 AC-2, FR-009.7 (skipped alert_key index), FR-011 (view exposes `alerted.v1` for the not_alerted gate; grounding fields need no DDL); NFR-002 (idempotency), NFR-003 (least privilege, append-only), NFR-004, NFR-005 (guard rejects any non-investigation row from the investigator and any investigation row from other roles), NFR-006 (no secret literal beyond the synthetic demo file).

## Change notes
- v1.1 (2026-11-24, Requirements Sync, PLAN-002): step 1 suppresses the `set_config` result so the password is never printed to migrate output. RR-15 (psql echoing the failing statement on error) is unchanged. CI asserts the password is absent from `docker compose logs migrate` (NFR-006).
