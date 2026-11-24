# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Synthetic-data AML/KYC demo (Phases 1–5): Redpanda (Kafka) → Python consumers → PostgreSQL audit trail, Redis velocity windows, FastAPI on `127.0.0.1:8000`, plus a recommend-only investigation agent on `alerts` and an analyst console (`/console`). Use synthetic data only; Compose credentials are local demo values.

## Commands

Everything runs inside Docker Compose (Docker Desktop, Linux containers). Code is baked into the image by `COPY *.py` — **rebuild after editing Python** (`docker compose up --build -d`); there is no source volume mount.

```powershell
docker compose up --build -d                                    # full stack (kafka, postgres, redis, migrate, scorer, api, ingest, investigator)
docker compose run --rm --entrypoint python ingest -m pytest -q # all tests (need the running stack: postgres/kafka/api hostnames)
docker compose run --rm --entrypoint python ingest -m pytest tests/test_rules.py::test_seed_totals -q   # single test
docker compose run --rm ingest seed                             # AML-1042 scenario: 2 credits ($83,800) then $80,900 debit
docker compose run --rm --entrypoint python ingest latency.py   # alert-latency gate (p95 < 500 ms over 40 scenarios)
docker compose run --rm ingest benchmark --seconds 60           # ingestion gate: ≥50 persisted rows/s with matching audit
docker compose run --rm ingest generate --rate 50 --seconds 120 # extra synthetic stream
docker compose logs scorer                                      # debug a service
```

CI (`.github/workflows/ci.yml`, job `benchmark`) runs, in order: `tests/compose_check.py` over `docker compose config` (base and `compose.anthropic.yaml` variants), `up --build -d`, a readiness curl, pytest, `migrate` a second time, `tests/egress_check.py` probes (investigator and scorer cannot reach `api.anthropic.com:443`; `watchlist-fetch` cannot reach `postgres:5432`), the Redpanda `enable_metrics_reporter=false` check, seed, latency.py, the `/alerts` `AML-1042` check, a stub `investigation.drafted.v1` row for AML-1042, then the benchmark. The `local-model` job (workflow_dispatch only) builds `llm` and checks local mode end to end. No linter is configured. Coding/commit conventions: see `AGENTS.md`.

Test split: `tests/test_rules.py`, the name-screening tests in `test_kyc.py`, `test_grounding.py`, `test_llm.py`, `test_eval_scenarios.py` and `test_egress_static.py` are pure; `test_database.py` needs postgres; onboarding/payment tests in `test_kyc.py` need api + kafka; `test_investigator.py` is mixed (pure config/row tests plus postgres stack tests via superuser + `SET ROLE aml_investigator`). `tests/conftest.py` clears the LLM env vars and blocks `anthropic.Anthropic`. `tests/egress_check.py` and `tests/compose_check.py` are CI tools, not pytest.

Config: `DSN`, `BROKER`, `TOPIC` are hard-coded in `pipeline.py` (not env). Phases 1–3 read only `SDN_FILE` (default `watchlists/sample.xml`). The investigator alone reads `LLM_MODE` (`stub` default | `local` | `anthropic`), `DATA_CLASSIFICATION` (`customer` default | `synthetic`; anthropic requires `synthetic`), `LOCAL_LLM_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ATTEMPTS`, `INVESTIGATOR_DB_HOST` and the secret files `/run/secrets/investigator_db_password` / `anthropic_api_key`. Compose secret sources: `INVESTIGATOR_DB_PASSWORD_SECRET`, `ANTHROPIC_API_KEY_SECRET` (default synthetic files under `secrets/demo/`). Never put a model default in compose (`LLM_MODEL: ${LLM_MODEL:-}`).

Networks: `internal` (`internal: true`) holds every service except `watchlist-fetch`; `api` also joins `ingress` to publish `127.0.0.1:8000` (the only host port); `egress` holds `watchlist-fetch` and, only via the override `compose.anthropic.yaml` (which also mounts the key secret), `investigator`. Every service must declare `networks:` explicitly. Profiles: `local` (`llm`, Ollama built from `llm.Dockerfile` with baked weights, `OLLAMA_MODEL` build arg default `qwen2.5:3b`) and `fetch` (`watchlist-fetch`). Nothing depends on a profiled service. Containers from the app Dockerfile run as non-root uid 10001.

Real OFAC list (optional): `docker compose --profile fetch run --rm watchlist-fetch` (the only service with internet; `ingest` has none), then set `SDN_FILE=watchlists/sdn.xml` and `docker compose up -d --force-recreate api scorer`. Tests assume the default fixture `watchlists/sample.xml` (fictional entries, e.g. "Cobalt Meridian Exports" hits, "Juniper Orchard Services" is clean).

## Architecture

- **`pipeline.py`** — shared constants (`BROKER`, `DSN`, `TOPIC`), synthetic `event()` generator (deterministic uuid5 IDs per run), producer, and the Phase 1 `ingest` consumer. `record_transaction()` is the single write path for transactions: `INSERT ... ON CONFLICT DO NOTHING`, and only a newly inserted row gets a `transaction.recorded` audit entry. Kafka offsets are committed only after the DB transaction commits. CLI entrypoint for the `ingest` service (`ingest|seed|benchmark|generate`).
- **`scoring.py`** — Quix Streams consumer (group `aml-scorer-v1`) on `transactions`. Per message, in one DB transaction: `record_transaction` → `payment_screen` (KYC) → reuse prior `scored.v1` result if this is a replay → Redis Lua script for 1-min/1-h event-time velocity (ZADD NX so retries count once, 48 h retention) → load 48 h of *already scored* account history → `rules.assess` → write `scored.v1` (+ `alerted.v1`). Alerts (score ≥ 60) go to the `alerts` topic, at-least-once.
  - `alerts` message = the `scored.v1` audit inputs: `{transaction_id, case_id, run_id, version, score, alert, rules:[{rule, points, evidence}]}`. No account field — join `transactions` by `transaction_id`. Quix publishes after the DB commit, so consumers must dedupe by `transaction_id` + rule version. Only `latency.py` (random group) consumes it today.
  - Topics are created by the one-shot `topic` service command in `compose.yaml`; add new topics there.
- **`rules.py`** — pure function `assess(row, minute_count, hour_count, history)`; seven illustrative rules with points, capped at 100. `rapid_pass_through` alone (65) triggers an alert. Unit-tested without infrastructure.
- **`kyc.py`** — Pydantic `Application` model (person/business, recursive `owners`), `review()` compares applicant vs document fields and screens applicant, differing document names, and every owner; `payment_screen()` screens an outbound counterparty once per (account, normalized name, snapshot hash). Screeners only record findings — nothing clears, blocks or closes cases.
- **`watchlist.py`** — parses OFAC legacy SDN XML via `defusedxml`, `normalize()` (casefold, strip accents/punctuation, sort tokens), RapidFuzz matching at threshold 88, snapshot versioned by SHA-256. `active()` is cached; restart services to change snapshot.
- **`api.py`** — `GET /alerts`, `GET /scores/{id}` (read from `audit`), `POST /onboarding` (idempotent by `application_id`; same ID + different payload → 409). Phase 5 console routes (`/console` page from `console.html`, `GET /console/queue`, `POST /console/decisions`) require HTTP Basic against the `analysts` secret (`name:password` lines, `ANALYSTS_SECRET`, default `secrets/demo/analysts`); the analyst name comes only from auth and is written as `actor=analyst:<name>`, action `analyst.decided.v1`, one per transaction (409 on repeat). `console.html` must render API values with `textContent` only (drafts are untrusted model output).
- **`investigator.py`** — confluent consumer (group `aml-investigator-v1`, manual commit after the DB commit) on `alerts`, connected as `aml_investigator` (never `pipeline.DSN`). `load_model_config` (mode, classification, synthetic gate, key/local checks) runs before any secret, socket, DB or Kafka; `load_config` adds the DB password, timeout and attempts. `handle`: parse the alert (pointer only) → txn 1 under advisory lock (dedupe pre-check, `alerted.v1` gate, evidence from DB) → model call outside any transaction → txn 2 (re-check, `INSERT ... ON CONFLICT DO NOTHING`, no RETURNING). Logs are JSON lines with keys `transaction_id|alert_key|outcome|attempts|latency_ms` only.
- **`llm.py`** — `StubLLM` (deterministic), `LocalLLM` (stdlib urllib to Ollama `/api/chat`, no proxy, no redirects), `AnthropicLLM` (lazy import, exact pin, `max_retries=0`), each with `params()`; `complete_with_retry` (bounded, backoff, backend-neutral `ModelError(tag, retryable)`, sanitized errors). `PROMPT_VERSION` lives here.
- **`grounding.py`** — pure strict `Draft`/`Finding` models, `check_grounding` (amounts, counterparties, rules, sanctions) and `consistency`.
- **`eval_investigator.py`** — opt-in real-model evaluation over `tests/eval/scenarios.json`; refuses unless anthropic + synthetic; no DB.

### Database invariants (`sql/`)

- `audit` is the system of record for every decision; `action` strings are versioned (`scored.v1`, `alerted.v1`, `kyc.reviewed.v1`, `onboarding.screened.v1`, `payment.screened.v1`, `investigation.drafted.v1`, `investigation.skipped.v1`, `analyst.decided.v1`). `004-investigation.sql` adds the `aml_investigator` role, the `investigator_audit` view, one-draft/one-outcome-per-alert indexes, a guard trigger, and triggers that block UPDATE/DELETE/TRUNCATE on `audit` for every role (tests must never do either). Partial unique indexes in `002-scoring.sql` enforce one ingestion/score/alert row per transaction — idempotency relies on them.
- `case_id` is NULL except seed case `AML-1042`, the only row in `cases`; `audit.case_id` is an FK to `cases` and `aml_worker` cannot INSERT into `cases`.
- `audit` already has unused `model_version` and `prompt_version` columns; the pgvector extension is installed but unused.
- App connects as `aml_worker`, which has only SELECT/INSERT (append-only audit). Don't write code that UPDATEs or DELETEs; grant changes go in SQL migrations.
- `001-foundations.sql` runs only via Postgres initdb on a fresh volume (initdb mounts only 001). `002`–`005` are re-run by the `migrate` service on **every** startup (one psql session; `004` needs the `investigator_password` psql variable from the secret), so new migrations must be idempotent (`IF NOT EXISTS`) and added to the `migrate` command in `compose.yaml`.
