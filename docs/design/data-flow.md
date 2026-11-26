---
id: "ARCH-002"
title: "Data Flow"
type: "architecture"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "architecture-author-agent"
references_adrs: ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006", "ADR-007", "ADR-008", "ADR-009", "ADR-013", "ADR-016", "ADR-017", "ADR-018", "ADR-019", "ADR-020", "ADR-021", "ADR-022", "ADR-023", "ADR-024", "ADR-025", "ADR-027", "ADR-028", "ADR-029", "ADR-030"]
---

# ARCH-002: Data Flow

Primary path traced: one synthetic transaction published to `transactions`, scored, alerted, and (PHASE 4, proposed) investigated. This is the system's main "call"; the HTTP endpoints only read results (`GET /scores/{id}`, `GET /alerts`, api.py:10-24). Status tags as in ARCH-001: BUILT, PHASE 4. See ARCH-001 sections 6-8 for threats and residual risks. Decisions are recorded in `docs/design/adrs/` (see `references_adrs`); the D-to-ADR mapping is D1 -> ADR-017 (D9 also in ADR-017), D2 -> ADR-018, D3 -> ADR-019, D4 -> ADR-020, D5 -> ADR-021, D6 -> ADR-022, combined index -> ADR-023, D7 -> ADR-024, D8 -> ADR-025, D10 -> ADR-026, D11 (hallucination controls, FR-011) -> ADR-027.

Worked example: `python pipeline.py seed` emits the AML-1042 scenario: two credits ($48,200 and $35,600 = $83,800) then an $80,900 debit (pipeline.py:11-13,121). The debit is 96.5% of inflows, inside the 75%-125% band (rules.py:12), so `rapid_pass_through` (65 points) fires and alerts at score >= 60 (rules.py:29,31).

## 1. Entry

1. CLI: `docker compose run --rm ingest seed` -> `pipeline.py` `__main__` (pipeline.py:108-121) -> `produce()` (pipeline.py:29).
2. `produce()` builds a `Producer` with `enable.idempotence` (pipeline.py:31), waits for topic metadata (pipeline.py:39), and for each event calls `event()` (pipeline.py:16-26: deterministic `uuid5(run, i)` id, `account`, `counterparty`, `amount_cents`, `direction`, `channel`, ISO `occurred_at`). Seed events use account `DEMO-1042`, case `AML-1042`, fixed 2026-11-14 timestamps (pipeline.py:21-23).
3. Message is published with key = account (pipeline.py:44) to the 1-partition `transactions` topic (compose.yaml:14), then `flush(30)` (pipeline.py:46). Boundary B2 (ARCH-001).

Two consumer groups read `transactions` independently: `aml-ingest-v1` (ingest) and `aml-scorer-v1` (scorer).

## 2. Initialization

| Service | Construction | Ref |
|---------|--------------|-----|
| ingest | `Consumer` group `aml-ingest-v1`, earliest, auto-commit off; one autocommit psycopg connection as `aml_worker` | pipeline.py:66-70 |
| scorer | confluent_kafka `Consumer` group `aml-scorer-v1`, earliest, manual commit, plus an idempotent `Producer` with `linger.ms=1` (ADR-032); Redis client registers Lua `VELOCITY`; psycopg connection, `dict_row` | scoring.py:26-29 |
| scorer wiring | `consumer.consume(500, timeout=0.02)` -> `score_batch` in one `db.transaction()` -> `forget_counts` -> produce alerts, `flush`, check delivery errors -> `consumer.commit(asynchronous=False)` | scoring.py `run` |
| watchlist | First `active()` call parses `SDN_FILE` (default `watchlists/sample.xml`) with `defusedxml`; cached by (path, mtime, size); version = SHA-256 | watchlist.py:94-102,68-91 |
| startup order | topics and migrations complete before scorer/api (`depends_on`) | compose.yaml:11-16,34-41,48-51,60-61 |
| investigator (PHASE 4) | Builds its DSN from `INVESTIGATOR_DB_HOST` and the password in `/run/secrets/investigator_db_password` (`INVESTIGATOR_DB_PASSWORD_FILE`; fails fast if missing, no fallback to `aml_worker`); `DATA_CLASSIFICATION` gate first (section 2a); `LLM_MODE` (`stub` default; `local` needs `LOCAL_LLM_URL` and `LLM_MODEL`; unknown value fails fast); key from `/run/secrets/anthropic_api_key` only if `anthropic` and the gate passed; asserts `alerts` has 1 partition; `Consumer` group `aml-investigator-v1`, `enable.auto.commit=false`; `max.poll.interval.ms >= LLM_TIMEOUT_SECONDS x LLM_MAX_ATTEMPTS + backoff + 60 s` | D1, D2, D5, D6, FR-010 |

### 2a. DATA_CLASSIFICATION startup gate (PHASE 4, FR-010.6, NFR-008.3(a))

Order of investigator (and `eval_investigator.py`) startup in `load_config`, a pure function so it is testable without I/O. Nothing below a failed step runs.

1. Read `DATA_CLASSIFICATION`. A value outside the allowed set (e.g. `bogus`) exits non-zero in any mode (FR-010.6 AC-4).
2. Read `LLM_MODE`; unknown value exits non-zero (FR-010.1).
3. If `anthropic`: require `DATA_CLASSIFICATION == "synthetic"`; unset or `customer` exits non-zero here, BEFORE the key file path is opened and before any client or socket is created (FR-010.6 AC-1, NFR-008 AC-3).
4. If `local`: require `LOCAL_LLM_URL` and `LLM_MODEL` (FR-010.5 AC-1/2); never read a key.
5. Only then, in CS-008 order: in anthropic mode read the key file (CS-008 step 3), then read the DB password file (CS-008 step 4), build the DSN, open DB and Kafka connections. The post-gate order is otherwise immaterial; the gate-first invariant is what matters.
6. Every `investigation.*.v1` row records `inputs.data_classification` (anthropic mode, per FR-010.6 AC-3).

Network gate (independent): in the default Compose files the investigator has no route out. Only the opt-in `compose.anthropic.yaml` override adds it to `egress` (ARCH-001 1a). The two gates are separate on purpose.

## 3. Execution

### 3a. Ingest path (BUILT)

`ingest()` consumes batches of up to 100 (pipeline.py:72); inside one DB transaction it calls `record_transaction()` per message (pipeline.py:75-80), which does `INSERT ... ON CONFLICT(id) DO NOTHING RETURNING id` and, only if a row was inserted, writes the `transaction.recorded` audit row with Kafka origin (pipeline.py:52-59). A `msg.error()` raises (pipeline.py:77-78). After the transaction commits, `consumer.commit(asynchronous=False)` (pipeline.py:81).

### 3b. Scoring path (BUILT) - one DB transaction per poll, `score_batch()` (ADR-032)

The steps run once per batch (up to 500 messages, partition order); per-event work is in steps 4 and 6.

| Step | Action | Ref |
|------|--------|-----|
| 1 | `record_transactions()` for the batch (Kafka partition and offset in `transaction.recorded`), so ingest and scorer race safely: whichever inserts first writes the single `transaction.recorded` row (unique index) | scoring.py:32; sql/002-scoring.sql:3 |
| 2 | `payment_screen_batch()`: only for debits; insert (account, normalized counterparty, snapshot) `ON CONFLICT DO NOTHING`; if newly inserted, screen with RapidFuzz >= 88 and write `payment.screened.v1` | scoring.py:33; kyc.py:81-90; watchlist.py:47 |
| 3 | Replay check, one query for the batch: an event with a `scored.v1` row (or a duplicate earlier in the batch) reuses its `inputs` (no new rows; the replayed result is returned downstream so the alert can be re-published) | scoring.py:34-37 |
| 4 | Velocity, one Redis pipeline: stored first counts if present (retry), else `ZADD NX`, trim to 48 h, 1-min and 1-h counts at event time, stored until `forget_counts` runs after the commit | scoring.py:39,15-22 |
| 5 | History: one prefetch of the batch accounts' *scored* transactions, extended in memory as each event is scored | scoring.py:40-43 |
| 6 | `assess(row, minute_count, hour_count, history)` pure function: seven rules, score capped at 100, `alert = score >= 60` | scoring.py:44; rules.py:2-31 |
| 7 | COPY `scored.v1` (+ `alerted.v1` if alert) with actor `scorer-v1` and `inputs = result`; unique indexes make duplicates impossible | scoring.py:45-50; sql/002-scoring.sql:4 |

## 4. Result Assembly

- Result dict: `{transaction_id, case_id, run_id, version:"v1", score, alert, rules:[{rule, points, evidence}]}` (rules.py:30-31). It is both the `scored.v1` audit `inputs` and the `alerts` message body (scoring.py:53). It carries no account; consumers join `transactions` by `transaction_id`.
- Alert publication: the scorer produces the batch's alerts after its DB commit, flushes, then commits offsets (ADR-032), so delivery is at-least-once and a crash can duplicate or (before publish) delay but not lose a committed alert on replay (step 3 returns the stored result).
- Read side: `GET /alerts` returns the latest 100 `alerted.v1` inputs; `GET /scores/{id}` returns the `scored.v1` inputs (api.py:10-24).

### 4a. Investigation path (PHASE 4, proposed) - one alert, per message (D1)

1. Poll one message from `alerts`. Parse/validate; a non-JSON or schema-invalid payload gets `alert_key = alerts:<partition>:<offset>` and is recorded as `investigation.skipped.v1` (`malformed_alert`), then the offset commits (FR-009.7).
2. Short DB txn on the `aml_investigator` connection (reads go through the view `investigator_audit`, which exposes only `scored.v1`, `alerted.v1`, `payment.screened.v1`, `investigation.drafted.v1`, `investigation.skipped.v1` rows; the role has no SELECT on `audit`): `pg_advisory_xact_lock(hashtext(alert_key))`; pre-check for a drafted row (by `transaction_id`) or skipped row (by `alert_key`); if found, commit and commit offset (no model call). The investigator proceeds only if an `alerted.v1` row exists for the transaction; otherwise it records a skip (`not_alerted`) keyed by Kafka origin (`alerts:<partition>:<offset>`), so a forged alert cannot take a real alert's `alert_key`. Evidence comes from the DB, not the Kafka payload. Gather evidence: the transaction and account (`transactions`), 30 days / last 50 transactions of history, `scored.v1` rule evidence, `payment.screened.v1` rows for the account (FR-009.2). An unknown `transaction_id` is recorded as skipped (`unknown_transaction`, keyed by Kafka origin, `transaction_id` NULL to satisfy the FK, sql/001-foundations.sql:18). Commit (releases the lock).
3. Build the minimized payload: deny-by-default allow-list, account replaced by `SUBJECT_ACCOUNT`, strings capped at 256 chars with control characters stripped, at most 50 evidence ids per rule (longer lists truncated and marked `evidence_truncated`, never rejected), wrapped in a delimited `<evidence>` block (D3, D4). Compute SHA-256 of the exact payload (`evidence_sha256`) and `prompt_sha256` = SHA-256(system + "\n" + user), which therefore includes the evidence (CS-008).
4. Model call OUTSIDE any DB transaction, by `LLM_MODE`: Stub (deterministic, offline); Local (PHASE 4, FR-010.5): HTTP POST of the same prompt to `LOCAL_LLM_URL` (self-hosted `llm` service, Ollama, internal network only, weights baked in, no key), same timeout, attempts, backoff, validation, grounding and skip rules as anthropic, `model_version` = `LLM_MODEL`, an unreachable server counts as an attempt failure and ends as `model_failure` skip after `LLM_MAX_ATTEMPTS`; or Anthropic (only if the step-2a gate passed and the override file gave a route; `max_tokens` 16000, effort `low`, no `temperature`, SDK `max_retries=0`; refusal or max_tokens stop = `model_failure`; own loop: up to `LLM_MAX_ATTEMPTS` 3, exponential backoff with jitter, `LLM_TIMEOUT_SECONDS` 30). No tools or function calling (D6).
5. Validate output with a strict pydantic model (`extra=forbid`): `summary` <= 2,000 chars, `recommendation` in {`escalate_for_review`, `no_further_action_suggested`}, `cited_transaction_ids` subset of evidence ids, plus claim-level findings (FR-011, ADR-027). Invalid output is retried; after the attempts are exhausted the alert is skipped as `model_failure` (FR-009.4, FR-010.4).
5a. Hallucination controls (FR-011, ADR-027), after schema validation and before any write: (i) the checks apply to the summary AND every finding statement, deterministically against the evidence snapshot, with these pinned rules (CS-008): amounts: $-prefixed amounts are matched whole (never truncated) and compared in integer cents, a malformed $-amount fails, and each must equal an evidence amount or the sum of cited transactions; counterparties: double-quoted names must match evidence counterparties after `watchlist.normalize`, unquoted names are unchecked (residual, RR-21); rules: snake_case tokens must be fired rules, except the two recommendation values; sanctions: listed terms are allowed only if any screening hit exists, negations included; (ii) on failure, retry the model call within the same `LLM_MAX_ATTEMPTS` budget; (iii) if still ungrounded, skip with `grounding_failure` (permanent, like `model_failure`, RR-10); (iv) a `consistency_warning` is attached as an informational field and never overrides the recommendation; (v) the drafted row is labelled `ai_generated`, `requires_human_review` and with grounding results. Checks do not cover (RR-21): amounts written without "$", unquoted counterparty names, sanctions paraphrases outside the term list (e.g. "sanctionable", "watch list match"); semantic misstatements rely on human review. Offline evaluation: an evaluation set runs with the stub in CI, and an opt-in real-model run reports metrics to a local report only (nothing written to `audit` or sent elsewhere).
6. Short DB txn: advisory lock, re-check, then `INSERT ... ON CONFLICT DO NOTHING` of one row: actor `investigator-v1`, action `investigation.drafted.v1` (or `investigation.skipped.v1`), `model_version` = id returned by the API (`stub-v1` in stub mode), `prompt_version` = `investigation-prompt-v2`, `inputs` = {`draft` {`summary`, `recommendation`, `cited_transaction_ids`, `findings`} (CS-008), labels (`ai_generated`, `requires_human_review`, grounding), `consistency_warning` if any, `evidence_truncated` if any, `evidence`, `evidence_sha256`, `prompt_sha256`, params, `alert_key`}. For drafted rows `alert_key = transaction_id`. `case_id` is taken from the DB `scored.v1` row, never the payload; skipped rows for `malformed_alert`, `unknown_transaction` and `not_alerted` have `case_id` NULL. Commit.
7. Commit the Kafka offset after the DB commit.

Integrity (corrected): sql/004 creates (a) a unique index on `audit(transaction_id) WHERE action='investigation.drafted.v1'` and (b) a unique index on `((inputs->>'alert_key')) WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1')`. Because drafted rows carry `alert_key = transaction_id`, index (b) makes drafted and skipped mutually exclusive per alert key, and (a) enforces at-most-one draft per transaction, all in the database. The BEFORE INSERT guard is two-way: it rejects any row from `aml_investigator` whose actor is not `investigator-v1` or whose action is not one of the two, and rejects any `investigation.*` action or `investigator-v1` actor from any other role (D2). The advisory lock and pre-check only avoid duplicate model calls; `ON CONFLICT DO NOTHING` (no target, so it covers both indexes; no `RETURNING`, since the role cannot SELECT `audit`) makes a lost race a harmless no-op.

## 5. Completion / Cleanup

- BUILT: ingest commits the offset after each batch commit (pipeline.py:81); the `finally` closes the consumer (pipeline.py:82-83). The scorer commits offsets itself after the DB commit and the alert flush (ADR-032). psycopg connections are context-managed (pipeline.py:70; scoring.py:29; api.py:12,22,35).
- Failure: an exception in `score()` rolls back the transaction; the message is redelivered; step 3 and the unique indexes make the retry safe. Compose restarts ingest/scorer `on-failure` (compose.yaml:52,68). A malformed message crash-loops (RR-7).
- PHASE 4: offset commits only after the audit INSERT commits. A crash before that redelivers; the pre-check or indexes then turn it into a no-op. The investigator never publishes to Kafka, writes no `cases`, and does not touch `scored.v1`/`alerted.v1` (D9, FR-009.6). Outcome: every consumed alert ends with exactly one drafted or skipped record.
- Retention: audit rows are permanent (at least 5 years, no deletion path, UPDATE/DELETE/TRUNCATE blocked by trigger, D7/D8).

## 6. Sequence Diagram

```
Producer   Redpanda      ingest        scorer        Redis     Postgres      investigator(P4)   Anthropic(P4)
   |  transactions msg      |             |             |           |               |                |
   |--produce(key=acct)--->|             |             |           |               |                |
   |   pipeline.py:44      |--consume--->|             |           |               |                |
   |                       |             |--record_transaction---->| (txn.recorded)|                |
   |                       |--consume------------------>           |               |                |
   |                       |                  BEGIN (per poll)     |               |                |
   |                       |                  |--record_transactions>| ON CONFLICT  |                |
   |                       |                  |--payment_screen_batch> payment.screened.v1 (debit)   |
   |                       |                  |--SELECT scored.v1--->| new ids => continue           |
   |                       |                  |--Lua VELOCITY (pipe)>|  counts        |                |
   |                       |                  |--history SELECT----->|  (once)        |                |
   |                       |                  |  assess() (pure)     |               |                |
   |                       |                  |--INSERT scored.v1, alerted.v1------->|                |
   |                       |                  COMMIT                 |               |                |
   |                       |<--alerts msg (after commit)------------|               |                |
   |                       |                                          |               |                |
   |                       |--poll alert---------------------------------------------->|                |
   |                       |                                          |<--txn: lock+precheck+evidence-|
   |                       |                                          |--COMMIT------>|                |
   |                       |                                          |               |--build payload |
   |                       |                                          |               |--HTTPS, timeout 30s, <=3 tries-->|   (anthropic: gate passed + egress override)
   |                       |                                          |               |--HTTP LOCAL_LLM_URL--> llm (internal)   (local mode; no egress)
   |                       |                                          |               |<--JSON output--|
   |                       |                                          |               |  validate (strict pydantic)
   |                       |                                          |               |  grounding checks; fail => retry => skip grounding_failure
   |                       |                                          |<--txn: lock+recheck+INSERT ON CONFLICT DO NOTHING
   |                       |                                          |--COMMIT------>|                |
   |                       |<--commit offset (after DB commit)----------------------|                |
   |                       |                                          |               |                |
 HTTP client --GET /alerts, /scores/{id}--> api --SELECT audit (aml_worker)--> returns inputs (api.py:10-24)
 (P4 rows are read from audit; no new endpoint, FR-009.8)
```

## 7. Data Elements and Classification

| Element | Where | Sensitivity (synthetic today) | Reaches model? |
|---------|-------|-------------------------------|----------------|
| account, counterparty, amount, direction, channel, occurred_at | `transactions`, Kafka | Account identifiers, transactional data | Yes, allow-listed; account aliased `SUBJECT_ACCOUNT` |
| rule hits and evidence ids | `audit` `scored.v1` | Decision data | Yes (rule name, points, evidence) |
| screening results | `audit` `payment.screened.v1` | Third-party names, list matches | Yes: entry_id, matched_name, score, disposition, snapshot hash |
| KYC application (name, DOB, id_number, address) | `kyc_applications` (api.py:37-39) | Highest (GLBA NPI in a real system) | No; role cannot read the table or onboarding audit rows (view `investigator_audit`, D2, D4); out of scope (FR-009.8) |
| model summary, findings, labels | `audit` `investigation.*.v1` | Untrusted text, grounding-checked for amounts/names/rules/sanctions wording only | Output |
| API key, DB passwords | secret files / compose values | Secret | Never logged or audited (D5); the key is never read in stub or local mode (FR-010 AC-9) |
| OFAC SDN list | `./watchlists/*.xml` | Public data | N/A, never sent to the model; flows fetch -> files -> api/scorer only (section 9) |

## 8. Onboarding Path (BUILT, brief)

`POST /onboarding` -> pydantic `Application` validation (kyc.py:31-42) -> `review()` (mismatches + screening of applicant, differing documents, every owner, kyc.py:51-78) -> `INSERT kyc_applications ... ON CONFLICT DO NOTHING`; a conflict with differing payload returns 409, same payload returns the stored result (api.py:37-45); otherwise audit `kyc.reviewed.v1` and one `onboarding.screened.v1` per subject (api.py:46-48). Not linked to accounts or alerts (FR-009.8).

## 9. OFAC Fetch Hand-off (PHASE 4, NFR-008.3(b))

```
 operator --docker compose --profile fetch run --rm watchlist-fetch--> [egress net] --HTTPS GET--> OFAC
      watchlist.refresh(): 128 MiB cap, defusedxml parse, Record_Count check (watchlist.py:16,88-90,105-116)
      atomic os.replace --> ./watchlists/sdn.xml   (the container's only write mount)
 container exits (one-shot; no secrets, no DB, not on internal)
 operator: SDN_FILE=watchlists/sdn.xml docker compose up -d --force-recreate api scorer   (PowerShell: $env:SDN_FILE=...)
 api, scorer (internal net) read ./watchlists READ-ONLY --> watchlist.active(): cached by (path, mtime, size); SHA-256 = snapshot version
```

1. Fetch runs only on explicit operator command (profile `fetch`); `up -d` never starts it. It opens no DB connection and sends nothing but an HTTP GET (no customer data crosses this boundary, B17).
2. The hand-off is the filesystem: write mount in `watchlist-fetch`, read-only mount in `api` and `scorer` (compose.yaml:46,57). Nothing on the internal network ever talks to the egress network, except `investigator` when started with `compose.anthropic.yaml` (ADR-030).
3. Consumers pick the new snapshot after recreate (or a changed mtime/size key, watchlist.py:94-102); every screening records the snapshot SHA-256, so the hand-off is auditable (watchlist.py:91).
4. Failure: an incomplete or oversize download is rejected before replace; the previous file stays in place.
