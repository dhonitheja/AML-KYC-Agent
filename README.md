# Real-time AML/KYC Agent · Phases 1 through 6

Synthetic-data engineering demo. The Python producer sends account-keyed transactions to Redpanda. A Python consumer commits transactions and their audit records in one PostgreSQL transaction before acknowledging Kafka offsets. Replayed event IDs are ignored. The application login can append to the audit table but cannot update or delete entries. Database administrators retain control. Redis tracks event-time velocity. FastAPI listens on host loopback port 8000. Compose credentials are local demonstration values.

## Run on Windows with Docker Desktop in Linux container mode

Open PowerShell inside the extracted project folder.

```powershell
docker compose up --build -d
docker compose run --rm ingest seed
docker compose run --rm ingest benchmark --seconds 60
docker compose exec postgres psql -U postgres -d aml -c "SELECT counterparty, direction, amount_cents, occurred_at FROM transactions WHERE case_id='AML-1042' ORDER BY occurred_at;"
docker compose down
```

The seed sends two credits totaling $83,800 followed by an $80,900 debit the next day. Rerunning the seed preserves the three transaction identities. Named volumes retain records across normal restarts. The benchmark uses a fresh run ID and offers 60 events per second. It counts durable transaction rows and matching audit entries through the end of the run, includes startup and drain time, and exits successfully only when all records arrive with average persisted throughput of at least 50/s. This measures phase 1 ingestion, not scoring latency. To stream additional data use `docker compose run --rm ingest generate --rate 50 --seconds 120`.

The browser POC is separate. The scorer runs independently of any model. The Phase 4 investigation agent defaults to an offline stub. Phase 5 adds the analyst console. No model credentials or real customer data are needed.

## Phase 2 · scoring and alerts

The scorer (8 replicas over a 16-partition `transactions` topic, Phase 6) scores account-keyed arrivals using 48 hours of previously scored account history. Seven illustrative rules cover rapid pass-through, large transfers, large cash activity, one-minute and one-hour velocity, repeated amounts, and debits after credits from multiple counterparties. Scores of 60 or more produce a Kafka message on `alerts` with the triggering transaction ID and evidence. Redis counts each event ID once in rolling event-time windows and retains two days of activity. Older late arrivals can have incomplete velocity context. Subsequent arrivals do not retrospectively rescore earlier transactions.

PostgreSQL records ingestion, scoring and alert decisions. A replay reuses the original decision. Alerts are delivered at least once. Downstream consumers should deduplicate by transaction ID and rule version. The migration runs during Compose startup on both new and existing Phase 1 databases. The API has read-only routes for the latest 100 alerts and individual transaction scores. Run locally with synthetic data.

After starting Compose, run these PowerShell commands:

```powershell
docker compose run --rm --entrypoint python ingest -m pytest -q
docker compose run --rm --entrypoint python ingest latency.py
Invoke-RestMethod http://localhost:8000/alerts
```

CI runs a warm-up, then 40 independent Northstar scenarios on isolated account keys. It measures from just before the triggering debit is published until the benchmark consumer receives its matching alert, including broker, Redis and database work. Missing alerts, missing pass-through evidence or p95 of 500 ms or more fail CI. This tests the seeded scenario. The 1,000 transactions/s load test is Phase 6.

## Phase 3 · KYC onboarding and screening

Rapid pass-through alone triggers a transaction alert (65 points against the 60-point alert threshold). Screening findings are separate audit events. A name similarity hit identifies a candidate for analyst review. An agreeing or conflicting full birth date is recorded with the match. Neither the screener nor the scoring service clears, blocks, or closes a case.

With Compose running, open http://localhost:8000/docs and submit a synthetic person or business to **POST /onboarding**. Use a UUID as the application ID. Provide the declared identity and at least one document's extracted fields. A person needs a birth date. A business can supply recursively nested owners. Documents are submitted as structured fields; the endpoint compares name, birth date, ID and address. It screens the applicant, document name variants, and each owner. Reusing the same ID and payload returns the original result. Changed input under that ID returns HTTP 409.

The demo and CI use fictional SDN-format entries in `watchlists/sample.xml`. Try “Cobalt Meridan Exports” to see a spelling-variant hit, or “Juniper Orchard Services” for a clean control. The stream screens an outbound counterparty on first encounter for each account and list snapshot. Results include snapshot SHA-256, entry ID, matched name or alias, similarity score and reasoning. Normalization ignores case, accents, punctuation and word order. The illustrative threshold is 88/100. Similar names alone cannot establish identity.

To load the public [OFAC SDN XML list](https://ofac.treasury.gov/sanctions-list-service), use the following PowerShell commands after building the image. The loader validates a download before replacing the local file. Restart services to change the selected path. Repeat the first command to refresh an active snapshot; future counterparty encounters use its new hash. Historical findings retain their original snapshot ID.

```powershell
docker compose --profile fetch run --rm watchlist-fetch
$env:SDN_FILE = "watchlists/sdn.xml"
docker compose up -d --force-recreate api scorer
```

The automated screening tests run in fixture mode (the default). They submit applications to FastAPI and payments through Kafka, then check the recorded findings in PostgreSQL. Use synthetic identity documents and payment data only.

## Phase 4 · investigation agent

The `investigator` service consumes `alerts`, acts only on alerts confirmed by an `alerted.v1` audit row, and records exactly one advisory outcome per alert: `investigation.drafted.v1` (a narrative with claim-level findings) or `investigation.skipped.v1` (with a reason). It is recommend-only. It never clears, blocks or closes a case, writes `cases`, updates or deletes rows, or publishes to Kafka. Every draft passed schema, citation and grounding checks (amounts, quoted counterparties, rule names, sanctions wording) and is labeled `ai_generated` and `requires_human_review`. Every row records `inputs.data_classification`.

It connects as the least-privilege role `aml_investigator`. That role can read `transactions` and the `investigator_audit` view and append investigation rows only. Database triggers make `audit` append-only for every role. Migrations 002 to 004 run in `migrate` on every start, and Postgres initdb mounts only `001`. Existing volumes upgrade in place. All Dockerfile-built services run as non-root uid 10001.

### Modes

| `LLM_MODE` | Backend | Data that may be processed |
| --- | --- | --- |
| `stub` (default) | Deterministic offline templates, `model_version=stub-v1` | any |
| `local` | Self-hosted Ollama `llm` service inside the deployment | any |
| `anthropic` | Anthropic Messages API | synthetic only (`DATA_CLASSIFICATION=synthetic`, else the service exits before reading a key) |

Investigator environment variables: `LLM_MODE`, `DATA_CLASSIFICATION` (`customer` when unset, or `synthetic`), `LOCAL_LLM_URL` and `LLM_MODEL` (both required in local mode; anthropic defaults to `claude-opus-5-5`; stub ignores them), `LLM_TIMEOUT_SECONDS` (30), `LLM_MAX_ATTEMPTS` (3, range 1 to 10). The Compose secret sources are `INVESTIGATOR_DB_PASSWORD_SECRET` and `ANTHROPIC_API_KEY_SECRET`; both default to the synthetic files under `secrets/demo/`. The `OLLAMA_MODEL` build argument sets the baked model (default `qwen2.5:3b`). Empty values count as unset.

Local mode. The one-time build downloads the Ollama image and the model weights. At runtime the server pulls nothing.

```powershell
docker compose --profile local build llm
$env:LLM_MODE="local"; $env:LLM_MODEL="qwen2.5:3b"; $env:LOCAL_LLM_URL="http://llm:11434"
docker compose --profile local up -d
```

Anthropic mode (synthetic data only). It needs the override file, which adds the only outbound route and the key secret:

```powershell
$env:DATA_CLASSIFICATION="synthetic"; $env:LLM_MODE="anthropic"; $env:ANTHROPIC_API_KEY_SECRET="C:\path\to\key-file"
docker compose -f compose.yaml -f compose.anthropic.yaml up -d
```

If you use the override with `LLM_MODE` unset, the stub runs with a route out. No code path uses it.

Evaluation. `tests/eval/scenarios.json` runs against the stub in CI. To measure the real model on the same synthetic scenarios, run `docker compose -f compose.yaml -f compose.anthropic.yaml run --rm -v "${PWD}\eval:/out" --entrypoint python investigator eval_investigator.py /out/eval-report.json` with the variables above. The container user cannot write to `/app`, so the report goes to the mounted `eval\` folder (on a Linux host, also pass `-u "$(id -u)"`). It writes `eval-report.json` and prints the grounding-failure, citation-violation and recommendation-agreement rates. It refuses to run unless `LLM_MODE=anthropic` and `DATA_CLASSIFICATION=synthetic`.

### Networks

- `internal` (`internal: true`, no route out): every service except `watchlist-fetch`.
- `ingress`: `api` only. It exists only to publish `127.0.0.1:8000`, the only host port.
- `egress`: `watchlist-fetch` (profile `fetch`, no secrets, writes only `./watchlists`), plus `investigator` when you add `compose.anthropic.yaml`.

Redpanda usage reporting (`enable_metrics_reporter`) is disabled explicitly. The `--set redpanda.enable_metrics_reporter=false` flag on the `kafka` command only bootstraps fresh clusters. On v24.3.10 it is ignored for an existing `kafka-data` volume, so the `topic` one-shot also runs `rpk cluster config set enable_metrics_reporter false` on every start. The `internal` network also blocks it. CI asserts that the effective value is `false`.

On Linux hosts, `./watchlists` must be writable by uid 10001 for `watchlist-fetch` (Docker Desktop on Windows and macOS needs nothing).

### Residual risks (accepted for the synthetic demo)

- RR-15: on error, psql or Postgres logs can echo the statement that sets the investigator password.
- RR-19: Kafka is unauthenticated, so forged alerts create bounded `not_alerted` skip rows (no model call).
- RR-20: there is no provider DPA or zero-retention review. It applies only to synthetic deployments.
- RR-21: grounding checks are partial. Amounts without `$`, unquoted names and sanctions paraphrases are not checked, and human review is the control.
- RR-23: `api` has a technical outbound route through `ingress`. Its code makes no outbound calls.
- RR-24: anthropic-mode egress is not host-restricted.
- RR-25: the `llm` image is set to run as uid 10001. This is not yet verified against the pinned image; if it fails, the image runs as root (internal only, no port, no secrets).

RR-1, RR-2, RR-3 and RR-6 must be re-assessed before any real data is used (ADR-015 amendment).

The `llm` image is `ollama/ollama:0.40.17@sha256:ccc42bcd3d5fcf7ab0d532b300382154e1a4da56fc666bdb313b78ebdd912754`. Record the model digest from the build log (`ollama list`) after the first `docker compose --profile local build --progress plain llm`.

## Phase 5 · analyst console

Open `http://localhost:8000/console` and sign in with a demo analyst (`analyst1` / `synthetic-analyst-1` or `analyst2` / `synthetic-analyst-2`). The queue shows the newest 100 alerts without a decision, with the triggering rules, the transaction and the investigator draft or skip reason. Drafts are labeled as AI output. An analyst records one disposition per alert (`escalate`, `close_no_action` or `request_information`) with a rationale. The API appends an `analyst.decided.v1` audit row with `actor=analyst:<name>`, and a second decision on the same alert gets 409. Decisions never change `cases`, block payments or file reports.

Credentials come from the Compose secret `analysts`, one `name:password` per line. Point `ANALYSTS_SECRET` at your own file to replace the demo accounts. HTTP Basic over loopback is a demo control only (ADR-031). Replace it with an identity provider and TLS before any non-local use. Migration `005-console.sql` adds the one-decision-per-alert index and runs in `migrate` with the others.

## Phase 6 · 1,000 transactions per second

The scorer now runs as `SCORER_REPLICAS` processes (default 8) in one consumer group over a 16-partition `transactions` topic. Each poll scores up to 500 messages in one database transaction with batched writes (ADR-032, ADR-033). Messages stay keyed by account, so each account is still scored in order by one process, and replays still reuse the stored decision. `alerts` stays single-partition for the investigator.

```powershell
docker compose run --rm ingest loadtest --rate 1200 --seconds 60   # gate: all rows recorded and scored, >= 1,000 scored/s
```

The load test offers 1,200/s over 10,000 synthetic accounts that are new for each run, and counts until every transaction has its `transaction.recorded` and `scored.v1` rows. On a 16-thread laptop with fresh volumes it measured about 1,190 scored/s, and at least 1,585/s when offered 1,600/s, with alert latency p95 59 ms. Per-push CI runs a 300/s smoke version. The full gate is the manual `load-test` workflow job; pick a larger runner with its `load_runner` input, since a standard 4-vCPU runner is expected to fall short. Stop the investigator while measuring (`docker compose stop investigator`), because it is a separate consumer and drains alerts on its own schedule.

Throughput depends on the database fitting in memory and on how much history each account carries. A 2.8 GB local database measured about 600/s, and 100 history-heavy accounts measured about 700/s (NFR-009). Measure on fresh volumes (`docker compose down -v`). An existing volume keeps its single-partition `transactions` topic, so it runs with one active scorer until you drain it and run `rpk topic add-partitions transactions --num 15`.

## Built with

- [Claude Code](https://claude.com/claude-code) wrote the Phase 5 and Phase 6 changes. Its commits carry a `Co-Authored-By: Claude` trailer.
- [CodeRabbit](https://www.coderabbit.ai) and [Codex](https://openai.com/codex) review pull requests automatically. Fixes for their findings are separate commits.
