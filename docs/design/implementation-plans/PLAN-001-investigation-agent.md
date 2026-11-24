---
id: "PLAN-001"
title: "Phase 4 investigation agent with hallucination controls"
type: "implementation-plan"
status: "superseded"
tier: "complex"
version: "1.0"
created: "2026-11-23"
author: "architect-planner-agent"
change_request: "Implement the Phase 4 investigation agent (FR-009/010/011) with hallucination/grounding controls as signed off"
addresses_fr: [FR-009, FR-010, FR-011]
addresses_nfr: []
addresses_us: [US-016, US-017, US-018, US-019, US-020, US-021, US-022, US-023, US-024, US-025, US-026, US-027]
constrained_by_adrs: [ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026, ADR-027]
proposes_new_adrs: []
proposes_new_requirements: []
supersedes: ""
superseded_by: "PLAN-002"
---

# PLAN-001: Phase 4 investigation agent with hallucination controls

## Summary
This plan adds the Phase 4 `investigator` service. It consumes `alerts`, uses the database to confirm an `alerted.v1` row exists, and builds minimized evidence from the DB only. It drafts a recommend-only narrative through `llm.py` (stub by default, Anthropic opt-in), runs the deterministic grounding checks in `grounding.py`, and appends exactly one `investigation.drafted.v1` or `investigation.skipped.v1` row per alert. It runs as the new least-privilege `aml_investigator` role, and DB triggers make `audit` immutable.

- **Tier:** complex (confirmed by the user at feature-intake).
- **ADR impact:** no new ADRs. ADR-017..027 are accepted and constrain this plan. The ADR-022 amendment dated 2026-11-23 is applied: no `temperature`, `max_tokens=16000`, `effort` low, refusal/max_tokens are non-retryable, no `fallbacks`, default `claude-opus-5-5`, exact pin found with `pip index versions anthropic`.
- **Security impact: YES.** There are three new trust boundaries:
  - (1) investigator to Anthropic API egress (ARCH-001 B12), with model output coming back as untrusted text (B13);
  - (2) the Docker secret files `investigator_db_password` and `anthropic_api_key` (B8, B8a);
  - (3) the new DB role `aml_investigator`, with the view, the guard trigger and the immutability triggers (B11).
  - The `alerts` topic becomes an untrusted trigger (B10). See Security Considerations.
- **Rows covered:** ARCH-001 (`docs/design/architecture-overview.md`) rows B8, B8a, B10, B11, B12 and B13.

## Requirements Addressed
| Req ID | Title | Relevant ACs -> Task / Test |
|---|---|---|
| FR-009.1 | Consumer | AC-1 C7/T5 pure (`consumer_config`); AC-2 C7/T5 stack (failure before txn-2 commit, re-handle gives one row) |
| FR-009.2 | Evidence gathering | AC-1 C7/T5 stack + C10 CI (AML-1042: 2 credits + debit ids); AC-2 C7/T5 pure (screening snapshot hash); AC-3 C7/T5 stack + T4 |
| FR-009.3 | Narrative output | AC-1 C7/T5 pure `build_drafted_row`; AC-2 C6/T2 (enum); AC-3 C7/T5 pure |
| FR-009.4 | Citation integrity | AC-1 C6,C7/T2 + T5 stack (stub cites fabricated id, no drafted row) |
| FR-009.5 | One draft per txn | AC-1 T5 stack (call-counting stub); AC-2 C1,C10 (CI runs `migrate` twice); AC-3 T5 stack (duplicate insert raises UniqueViolation, rollback); AC-4 T5 stack |
| FR-009.6 | Recommend-only | AC-1 T5 stack (scored/alerted rows byte-identical); AC-2 C1/T5 stack (`has_table_privilege`) |
| FR-009.7 | Skipped alerts | AC-1..AC-7 C7/T5 pure (`build_skipped_row`, reason enum, alert_key) + T5 stack (unknown, malformed, redelivered bad alert) |
| FR-009.8 | No onboarding data | AC-1 C7/T5 pure (evidence keys) + T5 stack (role cannot read `kyc_applications`) |
| FR-009.9 | Forged alerts (W2) | AC-1..AC-3 C7/T5 stack + T4 `forged_not_alerted` |
| FR-009.10 | Long evidence (W1) | AC-1..AC-3 C7/T5 pure + T4 `many_credit_ids` |
| FR-010.1 | Mode selection | AC-1, AC-2 C7/T5 pure `load_config` |
| FR-010.2 | Deterministic stub | AC-1 C5/T3; AC-2 T1 guard + C10 (no key in CI) |
| FR-010.3 | Real mode opt-in | AC-1, AC-4..AC-11 C7/T5 pure `load_config` (tmp files, monkeypatched env); AC-2 T5 stack (`stub-v1`, `investigation-prompt-v2`); AC-3 T5 stack (key absent from audit rows and caplog) |
| FR-010.4 | Bounded calls | AC-1 T5 stack (forced-raise stub); AC-2 C5/T3 (timeout passed to client, retryable); AC-3, AC-4, AC-5 C5/T3 |
| FR-011.1 | Claim-level output | AC-1..AC-3 C6/T2 |
| FR-011.2 | Grounding checks | AC-1..AC-4 C6/T2; AC-5, AC-7 C5,C7/T3 + T5 pure; AC-6 T2 (call-counting stub) |
| FR-011.3 | Consistency flag | AC-1..AC-3 C6/T2 |
| FR-011.4 | Labeling | AC-1, AC-2 C7/T5 pure + stack |
| FR-011.5 | Evaluation set | AC-1, AC-2, AC-5 C8/T4; AC-3 C8/T4 (`main()` refuses unless `LLM_MODE=anthropic`); AC-4 C8/T4 (script never imports psycopg) |

User stories US-016..US-027 are covered through these FRs. The FR/US mapping is in `docs/requirements/traceability-matrix.md`.

## ADR Guardrails
| ADR | Decision | How this plan respects it |
|---|---|---|
| ADR-017 | Single-process confluent consumer, commit after DB | C7: group `aml-investigator-v1`, auto-commit off, one message at a time, model call outside DB txns |
| ADR-018 | `aml_investigator` role, `investigator_audit` view, two-way guard | C1; C7 never uses `pipeline.DSN`, `RETURNING` or SELECT on `audit` |
| ADR-019 | Untrusted input/output | C7 `<evidence>` delimiting + escaping; C6 strict pydantic `extra=forbid` |
| ADR-020 | Allow-list, `SUBJECT_ACCOUNT` alias, payload hash | C7 `build_evidence`, `evidence_sha256`, `prompt_sha256` |
| ADR-021 | Docker secret files, env fallback for dev only | C2, C3, C7 `load_config` |
| ADR-022 (+ amendment 2026-11-23) | Exact SDK pin, own retry, fixed params, recorded versions | C5, C9 (facts block under C5) |
| ADR-023 | Combined partial unique index for draft/skip | C1 `audit_investigation_alert_once` |
| ADR-024 | Immutability triggers | C1; tests never TRUNCATE/UPDATE/DELETE |
| ADR-025 | Retention, no deletion path | No delete code; C11 documents the residual risks |
| ADR-026 | Non-root uid 10001 | C4 |
| ADR-027 | Grounding controls + eval set | C6, C8 |

## ADR Conflicts (if any)
None. The ADR-022 amendment (2026-11-23) has already corrected the earlier `temperature` and `max_tokens` wording. This plan follows the amended text, and CS-009 agrees with it.

## Security Considerations
| Concern | Control | Where it lands |
|---|---|---|
| Egress of evidence to a third party (B12) | Off by default (`LLM_MODE=stub`). Deny-by-default allow-list, `SUBJECT_ACCOUNT` alias, no KYC data, strings capped at 256 chars with control chars stripped, history capped at 50/30 days, at most 50 rule ids per rule. The exact payload and its SHA-256 are stored. RR-20 (no DPA) is accepted because the data is synthetic | `investigator.build_evidence`, `render_prompt` |
| API key secret (B8) | Read only when `LLM_MODE=anthropic`, from `ANTHROPIC_API_KEY_FILE`; the env var is a dev fallback only. The key is held only in `AnthropicLLM`. It never appears in logs, audit rows or exception text; errors are reduced to type name + status code | `investigator.load_config`, `llm.AnthropicLLM`, `llm._sanitize` |
| Investigator DB password (B8a) | A single secret file read by `migrate` (psql `\set`, `set_config(...,true)`) and by the investigator (`read().strip()`). No fallback to the `aml_worker` DSN; an empty file exits. RR-15 (psql echo on error) is accepted | `compose.yaml`, `sql/004`, `investigator.load_config` |
| New DB role (B11) | SELECT only on `transactions` and `investigator_audit`, plus INSERT on `audit` and USAGE on the sequence. A two-way BEFORE INSERT guard and UPDATE/DELETE/TRUNCATE triggers. No `RETURNING` | `sql/004-investigation.sql` |
| Forged / untrusted alert (B10) | The payload is only a pointer. An `alerted.v1` gate is required; rules and score come from the DB. Skips keyed `alerts:<p>:<o>` cannot squat a real slot. Malformed input is skipped, with no crash-loop | `investigator.handle` |
| Prompt injection / untrusted output (B13) | Delimited, escaped `<evidence>` and an "untrusted data" system prompt. No tools or streaming. Strict pydantic validation, citation subset check, grounding checks, then retry, then skip. The summary is stored as text and never rendered | `investigator.render_prompt`, `grounding.py` |
| New runtime dependency `anthropic` | Exact `==` pin from `pip index versions anthropic`; DI-010 covers provenance; lazy import in anthropic mode only | `requirements.txt`, `llm.py` |
| Container privilege | Non-root uid 10001; secrets mounted read-only | `Dockerfile`, `compose.yaml` |
| Committed secrets | `.gitignore` `secrets/*` + `!secrets/demo/`; demo values are synthetic and the demo API key file is empty | `.gitignore`, `secrets/demo/` |
| Open security NFRs touched | NFR-003, NFR-005, NFR-006 (`focus_track: security`). T5 stack tests close the NFR-003 gap (no UPDATE/DELETE) | T5 |

## Source File Changes

### C1 - sql/004-investigation.sql (new)
- **CS reference:** CS-010 (follow the DDL order exactly). **ACs:** FR-009.5 AC-2/AC-3, FR-009.6 AC-2, FR-009.8, FR-009.9.
- **What to change:** one BEGIN/COMMIT block with these steps:
  - `set_config('aml.investigator_password', :'investigator_password', true)`;
  - a DO block that runs CREATE ROLE if the role is absent, else ALTER ROLE PASSWORD;
  - `CREATE OR REPLACE VIEW investigator_audit`, with five actions including `alerted.v1`;
  - grants: SELECT on transactions and the view, INSERT on audit, USAGE on `audit_event_id_seq`;
  - the two `CREATE UNIQUE INDEX IF NOT EXISTS` indexes;
  - the functions `audit_investigator_guard` and `audit_immutable`, both with `SET search_path = pg_catalog, public` and neither SECURITY DEFINER;
  - three triggers, each created only if absent, guarded by a `pg_trigger` check.
- **Idempotent:** it must succeed when run twice.
- **Side effects:** the immutability triggers apply to every role. Existing tests only INSERT and roll back (verified), so they are unaffected.

### C2 - compose.yaml
- **CS reference:** CS-010, CS-008.
- **What to change:**
  - `postgres`: replace the `./sql` mount with `./sql/001-foundations.sql:/docker-entrypoint-initdb.d/001-foundations.sql:ro` only.
  - `migrate`: add `secrets: [investigator_db_password]`. Change the command to a shell form that runs one psql session: ``\set investigator_password `cat /run/secrets/investigator_db_password` ``, then `\i` 002, 003, 004 with `ON_ERROR_STOP=1`. For example, use `entrypoint: [sh, -ec]` and pipe the `\set` line plus the `\i` lines into `psql -v ON_ERROR_STOP=1 -f -`.
  - New `investigator` service: `build: .`, `entrypoint: [python, -u, investigator.py]`, `environment: {LLM_MODE: ${LLM_MODE:-stub}, LLM_MODEL: ${LLM_MODEL:-claude-opus-5-5}}`, `secrets: [investigator_db_password, anthropic_api_key]`, `depends_on` topic and migrate `service_completed_successfully`, `restart: on-failure`.
  - Top-level block:
    ```yaml
    secrets:
      investigator_db_password: {file: ${INVESTIGATOR_DB_PASSWORD_SECRET:-./secrets/demo/investigator_db_password}}
      anthropic_api_key: {file: ${ANTHROPIC_API_KEY_SECRET:-./secrets/demo/anthropic_api_key}}
    ```
- **Side effects:** a fresh volume now gets 002/003 from `migrate` only. That is safe because both are idempotent.

### C3 - secrets/demo/ and .gitignore
- **What to change:**
  - Add `secrets/demo/investigator_db_password` with a synthetic value (e.g. `synthetic-investigator-demo`) and a trailing newline.
  - Add `secrets/demo/anthropic_api_key` as an empty file.
  - Append to `.gitignore`: `secrets/*`, `!secrets/demo/`, `.jetro/`, `.claude-flow/`.
- **ACs:** FR-010.3 AC-3/AC-10, NFR-006.

### C4 - Dockerfile
- **CS reference:** CS-008 (deployment), ADR-026.
- **What to change:**
  - After `pip install`, add `RUN useradd --system --uid 10001 app && mkdir -p /app/state && chown app /app/state`. Quix Streams writes its default `state/` directory under `/app` (scoring.py:26), so it must be writable.
  - Add `ENV PYTHONDONTWRITEBYTECODE=1`.
  - Add `USER app` before `ENTRYPOINT`.
- **Side effects:** all services now run as uid 10001. Secret files must be readable by that uid; compose file secrets are bind-mounted with host permissions.

### C5 - llm.py (new)
- **CS reference:** CS-009, DI-010. **ACs:** FR-010.2, FR-010.4 AC-2..AC-5, FR-011.2 AC-5/AC-7.
- **Contents:**
  - `PROMPT_VERSION = "investigation-prompt-v2"`.
  - `StubLLM`: deterministic, built from the CS-009 templates. Test hooks: `script=[...]` per attempt (`"ok"`, `"raise"`, `"fabricated_id"`, `"ungrounded"`), plus a `calls` counter.
  - `AnthropicLLM(api_key, model, timeout)`, with a lazy `import anthropic`.
  - `Failure(attempts, error, failed_checks, last_reason)`.
  - `complete_with_retry(llm, system, user, validate, max_attempts, sleep=time.sleep, rng=random.random)`, with backoff `min(30, 2**(n-1)) * (0.5 + rng())`.
  - `_sanitize(exc) -> "<Type>[:<status>]"`.
- **SDK facts (verified from the official Claude API reference; copy exactly):**
  - `anthropic` 1.x is built on httpx2. The code author runs `pip index versions anthropic` and pins the exact latest 1.x with `==`. Never guess a version.
  - Client: `anthropic.Anthropic(api_key=key, max_retries=0, timeout=float_seconds)`.
  - Request: `client.messages.create(model=LLM_MODEL, max_tokens=16000, output_config={"effort": "low"}, system=system, messages=[{"role": "user", "content": user}])`.
  - Do NOT send: `temperature`, `top_p` or `top_k` (400 on current models), `thinking` (on by default; disabled is a 400), tools, streaming, `fallbacks`.
  - Response:
    - Check `response.stop_reason`: "refusal" or "max_tokens" is a non-retryable model_failure.
    - Text comes from blocks where `block.type == "text"`; thinking blocks are also present.
    - The model id is `response.model`.
    - The default model is `claude-opus-5-5`.
  - Retryable errors: `anthropic.APITimeoutError`, `anthropic.APIConnectionError`, `anthropic.RateLimitError`, `anthropic.APIStatusError` with status_code >= 500. Any other APIStatusError is a non-retryable model_failure.
  - Errors are sanitized to type name plus status code.
- **Classification order:** check `APITimeoutError` before `APIConnectionError`, because it is a subclass. Empty or missing text blocks count as a retryable validation failure. Never chain, log or store the original exception.

### C6 - grounding.py (new, pure)
- **CS reference:** CS-008 section "grounding.py". **ACs:** FR-009.3 AC-2, FR-009.4, FR-011.1..FR-011.3.
- **Contents:**
  - `Finding` and `Draft` pydantic models with `extra="forbid"`, including the summary-citation validator.
  - `check_grounding(draft, evidence) -> list[str]`, covering the checks `amounts`, `counterparties`, `rules` and `sanctions`.
  - `consistency(draft, evidence) -> str | None`.
- **Money regex (exact):** `\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|[.,]\d)`.
  - Parse each match to integer cents. A fractional part must have exactly 2 digits.
  - Malformed guard: the count of `\$\s?\d` matches must equal the regex match count.
  - Each amount must equal one evidence transaction's `amount_cents`, or the sum over the cited ids.
- **Other checks:**
  - Rule regex: `\b[a-z]+(?:_[a-z]+)+\b`, excluding the two recommendation values.
  - Sanctions terms: `sanction(s|ed)`, `OFAC`, `SDN`, `watchlist match`, `screening hit`; case-insensitive, word-bounded.
  - Counterparty names in double quotes must match after `watchlist.normalize`.
- **Imports:** `from watchlist import normalize`. Module import is side-effect free; `active()` is lazy and cached.

### C7 - investigator.py (new)
- **CS reference:** CS-008. **ACs:** all of FR-009, plus FR-010.1, FR-010.3, FR-010.4 AC-1, FR-011.4.
- **Pure functions:**
  - `load_config(env) -> Config`: exits non-zero on a bad mode, a missing key, a missing or empty password file, or an out-of-range timeout or attempts value. Reads the key only in anthropic mode, preferring the file over the env var.
  - `consumer_config(cfg)`.
  - `build_evidence`.
  - `render_prompt`.
  - `validate_draft(raw, evidence_ids, fired_rules)`.
  - `build_drafted_row`.
  - `build_skipped_row`: rejects any reason outside the five-value set.
  - `AlertIn`.
- **I/O functions:**
  - `handle(msg, db, llm, cfg)`: steps 0-6 of CS-008 (two short transactions, advisory lock, pre-check, `alerted.v1` gate, model call outside any transaction, bare `ON CONFLICT DO NOTHING`, `rowcount`). It takes `db` and `llm` as parameters so T5 can inject them.
  - `main()`: startup checks are `SELECT current_user = 'aml_investigator'` and `alerts` having exactly 1 partition. Then a poll loop that runs `consumer.commit(asynchronous=False)` after each `handle`.
- **Rules:** never import `pipeline.DSN`. JSON-line logging of only the id or alert_key, outcome, attempts and latency_ms. Set `SET LOCAL lock_timeout='5s'` and `statement_timeout='10s'`.

### C8 - eval_investigator.py (new) and tests/eval/scenarios.json (new)
- **CS reference:** CS-008 "Evaluation set". **ACs:** FR-011.5.
- **scenarios.json:** `"version": 1`, all ids are UUIDs, drafted scenarios set `db.alerted: true`. It has 8 scenarios: `AML-1042`, `clean`, `screening_hit`, `large_cash`, `injection_in_counterparty`, `malformed`, `many_credit_ids` (60+ ids), `forged_not_alerted`.
- **Shared gate logic:** put the alert gate in `investigator.py` as a pure `decide(alert_raw, txn, alerted, ...)` helper. `handle`, T4 and the eval script all reuse it, so the logic is not duplicated.
- **eval_investigator.py:** exits unless `LLM_MODE=anthropic` and a key is present. It does not import psycopg and opens no DB connection. It writes `./eval-report.json` (the path can be passed as an argument) and prints three rates: grounding-failure, citation-violation and recommendation agreement.

### C9 - requirements.txt
- Add `anthropic==<exact latest 1.x from pip index versions anthropic>`.
- Do not change the other pins.

### C10 - .github/workflows/ci.yml
- **Readiness wait:** after `up --build -d`, wait for the API with `curl --retry 30 --retry-connrefused --retry-delay 2 --fail http://localhost:8000/alerts >/dev/null`. Also check that `docker compose ps investigator` shows it running.
- **Migrate twice:** after pytest, run `docker compose run --rm migrate` a second time (FR-009.5 AC-2).
- **Drafted-row check:** after `seed`, poll for up to 60 s with `docker compose exec -T postgres psql -U postgres -d aml -tAc "SELECT count(*) FROM audit WHERE action='investigation.drafted.v1' AND case_id='AML-1042' AND model_version='stub-v1'"` until it returns 1 or more, else fail.
- **Mode:** no `LLM_MODE` and no key are set, so the job runs the stub.
- **Budget:** stay within `timeout-minutes: 15`.

### C11 - README.md and CLAUDE.md
- **README:** add a "Phase 4: investigation agent" section covering:
  - stub vs anthropic mode;
  - the secret file overrides `INVESTIGATOR_DB_PASSWORD_SECRET` and `ANTHROPIC_API_KEY_SECRET`;
  - the eval script;
  - recommend-only posture and human review;
  - residual risks RR-15/19/20/21;
  - the existing-volume note (re-run `migrate`).
- **CLAUDE.md:**
  - Phases 1-4.
  - Add `investigator.py`, `llm.py` and `grounding.py` to Architecture.
  - New env vars (the claim that the only env var is `SDN_FILE` is now false).
  - `004` is run by `migrate`, and initdb mounts only 001.
  - Non-root user.
  - Test split: `test_grounding`, `test_llm` and `test_eval_scenarios` are pure; `test_investigator` is mixed.
  - The new CI steps.

## New Test Scenarios
The test author writes these tests from the FR, CS and DI specs, in parallel with the code (see Ordering).

### T1 - tests/conftest.py (pure)
- An autouse fixture monkeypatches `anthropic.Anthropic`, if importable, with a stub that raises. No test can reach the network. It also deletes `ANTHROPIC_API_KEY` from the env.
- **ACs:** FR-010.2 AC-2.

### T2 - tests/test_grounding.py (pure)
- **FR:** FR-011.1..FR-011.3, FR-009.3 AC-2, FR-009.4.
- **Money cases:** a parametrized table of every CS-008 money case (19 strings, expected cents or MALFORMED), plus "$100000" against evidence of $100.00, which must fail. Also "$81,000" against $80,900.00 fails (FR-011.2 AC-1).
- **Other checks:**
  - a counterparty absent from evidence fails;
  - a rule named in text that did not fire fails;
  - "OFAC match" fails without a hit and passes with one;
  - `escalate_for_review` in text does not trip `rules`.
- **Schema:**
  - 0 or 11 findings rejected;
  - a statement over 300 chars rejected;
  - empty citations rejected;
  - a finding `rule` that did not fire rejected;
  - a summary id that is in no finding rejected;
  - an extra field rejected;
  - a bad recommendation rejected.
- **Consistency:** no-action with 60 points, or with a hit, gives a warning and leaves the recommendation unchanged. Escalate gives no warning.
- **No model call:** `check_grounding` leaves the stub `calls` counter unchanged (FR-011.2 AC-6).

### T3 - tests/test_llm.py (pure)
- **FR:** FR-010.2, FR-010.4, FR-011.2 AC-5/AC-7.
- **Stub:**
  - identical evidence gives byte-identical output;
  - stub output passes `check_grounding` for each drafted scenario;
  - a stub that cannot parse evidence raises.
- **Retry loop** (`sleep` and `rng` injected, no real sleeping):
  - success on attempt 2;
  - exhaustion after `max_attempts` with `Failure.attempts == max_attempts`;
  - `last_reason` follows the last attempt only: script `[ungrounded, raise]` gives `model_failure`, and `[raise, ungrounded]` gives `grounding_failure` with `failed_checks`;
  - a fabricated id on every attempt gives `model_failure`.
- **Anthropic fake** (monkeypatched `anthropic.Anthropic` returning a fake `messages.create`):
  - asserts the exact kwargs: `max_tokens=16000`, `output_config`, and no temperature/top_p/top_k/thinking/tools/stream/fallbacks;
  - asserts constructor kwargs `max_retries=0` and `timeout`;
  - joins only text blocks (a thinking block is ignored);
  - returns `response.model`.
- **Error classes:** build SDK errors with `cls.__new__(cls)` and set `status_code`, which avoids the SDK constructors.
  - 429/500/timeout/connection are retried;
  - 400/401/404 stop after 1 attempt;
  - `stop_reason` refusal or max_tokens stops after 1 attempt with `model_failure`.
- **Sanitized errors:** the sanitized error string contains no exception message (e.g. a planted `sk-...` string).

### T4 - tests/test_eval_scenarios.py (pure)
- **FR:** FR-011.5, FR-009.9, FR-009.10.
- **Scenario file:** it loads, `version` is an int, it has 8 or more scenarios covering all 8 names, and every id is a UUID.
- **Outcomes:** each scenario goes through `decide`, `build_evidence`, `StubLLM`, `validate_draft` and `check_grounding`, and the actual outcome must equal `expected`.
- **Specific scenarios:**
  - `many_credit_ids`: at most 50 ids, `evidence_truncated`, and the alerted id kept;
  - `injection_in_counterparty`: `</evidence>` is escaped in `user`, and the outcome is drafted or `grounding_failure`.
- **eval_investigator:** `main()` exits non-zero with `LLM_MODE` unset, and `psycopg` is not in the script's imports (checked via the AST). Together these cover AC-3 and AC-4.

### T5 - tests/test_investigator.py (pure + stack)
- **FR:** FR-009.1..FR-009.10, FR-010.1, FR-010.3, FR-010.4 AC-1, FR-011.4.
- **Pure:**
  - `consumer_config`: group and auto-commit off.
  - `load_config` matrix, using tmp files and monkeypatched env:
    - unset gives stub;
    - bogus mode exits;
    - anthropic with no key exits;
    - the file is preferred over the env var;
    - the env fallback works;
    - in stub mode the key file is never opened (pass a path that would raise);
    - an empty password file exits;
    - the host defaults to `postgres`;
    - in stub mode `LLM_MODEL` is ignored;
    - with anthropic mode and `LLM_MODEL` unset, the model is `claude-opus-5-5`.
  - `build_evidence`:
    - only allow-listed keys;
    - `SUBJECT_ACCOUNT`;
    - 256-char cap and control-char stripping;
    - no onboarding keys;
    - the snapshot hash is carried;
    - truncation at 60 ids and no truncation at 50 or fewer;
    - `evidence_ids` matches what was sent.
  - `build_drafted_row` labels: `ai_generated`, `requires_human_review`, and `grounding.checks` set to all four names with 1 to max attempts.
  - `build_skipped_row`: rejects an unknown reason; alert_key, origin and NULL `transaction_id`/`case_id` follow AC-5/AC-7.
- **Stack (needs postgres):**
  - **Connections:** an admin connection uses `postgresql://postgres:synthetic-demo@postgres/aml` and runs `SET ROLE aml_investigator` for the investigator role, so no secret is mounted into `ingest` (see Open questions). Fixture rows are written as `aml_worker` via `pipeline.DSN` and `record_transaction`, with a fresh `uuid4()` per test, plus `scored.v1`/`alerted.v1` rows as actor `pytest`.
  - **Fake messages:** a fake `msg` object with `value()`, `topic()`, `partition()=0` and a unique large `offset()` (e.g. `2**40 + random`), so `alerts:<p>:<o>` keys never collide with real offsets.
  - **Cases:**
    - one drafted row per alert, with `stub-v1` and `investigation-prompt-v2`;
    - redelivering the same message gives no second row and no second model call;
    - injecting a failure before the txn-2 commit, then re-handling, gives exactly one row;
    - a `model_failure` skip that is redelivered gives no call and no row;
    - unknown txn and malformed (non-JSON) give one skip each, and redelivery still gives one;
    - a forged alert (txn exists, no `alerted.v1`) gives a `not_alerted` skip with NULL ids, and a later genuine alert for the same txn is still drafted;
    - payload rules/score differ from `scored.v1`, and the evidence still equals `scored.v1`;
    - the forced-raise stub gives a `model_failure` skip and no drafted row;
    - the scored/alerted rows are byte-identical before and after;
    - the API key string is not found in audit `inputs` (`caplog` clean).
  - **Guard, in rolled-back transactions:**
    - `aml_worker` inserting an `investigation.drafted.v1` or `investigator-v1` row raises;
    - the investigator inserting a `scored.v1` row raises;
    - UPDATE, DELETE and TRUNCATE on `audit` raise (savepoint per statement), and an admin UPDATE raises too;
    - a duplicate drafted insert raises UniqueViolation;
    - `has_table_privilege('aml_investigator', ...)` is false for UPDATE/DELETE on audit and for SELECT on audit, `kyc_applications`, `cases` and `screened_counterparties`;
    - under the role, `SELECT FROM kyc_applications` raises InsufficientPrivilege.
- **Rule:** never TRUNCATE. Use rollback, or unique ids for committed rows.

## Ordering and Dependencies
1. The code author (C1-C11) and the test author (T1-T5) run **in parallel**. Both work from this plan and CS-008/009/010; the test author does not wait for code.
2. Within the code work: C9 and C4 first (image), then C1, C2, C3 (stack), then C6, then C5, then C7, then C8, and C10/C11 last.
3. **The code reviewer runs the full suite last:**
   - `docker compose up --build -d`;
   - `docker compose run --rm --entrypoint python ingest -m pytest -v`;
   - `seed`;
   - `latency.py`;
   - the AML-1042 drafted-row check;
   - the benchmark.
   It also reads the diff against the AC table above.

## Build & Test Verification
- Build: `docker compose up --build -d`.
- Test: `docker compose run --rm --entrypoint python ingest -m pytest -v`.
- Also run: `docker compose run --rm migrate` a second time, `ingest seed`, `latency.py` and `ingest benchmark --seconds 60`.
- Expected: all existing tests (test_rules, test_kyc, test_database) still pass, all new tests pass, and an AML-1042 drafted row exists in stub mode.

## Risk Assessment
- **Single-partition `alerts`.** Ordering and the single-writer assumption hold only with 1 partition. The investigator asserts this at startup and exits otherwise. Scaling out needs per-key ordering review plus a later ADR.
- **Existing volumes.** `aml_investigator` is created by `migrate`, not initdb, so an existing `pg-data` only needs `docker compose up` (migrate re-runs 004). If `migrate` fails (e.g. a missing secret), the investigator never starts, because it depends on `service_completed_successfully`. An old volume also keeps whatever initdb ran before; that is harmless because 002/003 are idempotent.
- **Non-root permissions.** Quix `state/` needs a writable `/app/state` (C4). Bind-mounted secrets and `watchlists/` must be readable by uid 10001; on Linux CI, checked-out files are world-readable. `watchlist.py` download writes `watchlists/sdn.xml` through a host volume and may need host permissions; document this in the README. The pytest cache is disabled by the read-only `/app`, which only produces a warning.
- **CI 15-minute budget.** New steps: readiness wait (at most 60 s), a second migrate (a few seconds), a drafted-row poll (at most 60 s), and the new tests (stub, fast). Keep stack tests few and avoid sleeps.
- **Existing tests.** The immutability triggers break any UPDATE/DELETE/TRUNCATE; none exist (verified in tests/ and *.py). `test_database.py` inserts `scored.v1` as actor `pytest` and rolls back, which the guard allows.
- **High-impact files.** `compose.yaml` and `Dockerfile` affect every service. `watchlist.normalize` is now shared with grounding, so changing it affects both.
- **Platform.** The README already uses PowerShell commands. The shell-form `migrate` command runs inside a Linux container, so it is unaffected.

## Open Questions
1. **How stack tests get investigator privileges.** The plan uses the postgres superuser plus `SET ROLE aml_investigator` (no secret mounted into `ingest`). The alternative is to mount `investigator_db_password` into `ingest` and connect as the role. Default: SET ROLE.
2. **Investigator log shape in CI.** The plan asserts the DB row only, not logs. That is enough unless log assertions are wanted.

## New Requirements (if any)
None. FR-009/010/011 and US-016..027 already cover every behaviour in this plan. On completion, Requirements Sync should flip FR-009/010/011 from `proposed` to built and fill `source_files`/`test_files`.
