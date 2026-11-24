---
id: "ARCH-001"
title: "Architecture Overview"
type: "architecture"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "architecture-author-agent"
references_adrs: ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006", "ADR-007", "ADR-008", "ADR-009", "ADR-010", "ADR-011", "ADR-012", "ADR-013", "ADR-014", "ADR-015", "ADR-016", "ADR-017", "ADR-018", "ADR-019", "ADR-020", "ADR-021", "ADR-022", "ADR-023", "ADR-024", "ADR-025", "ADR-026", "ADR-027", "ADR-028", "ADR-029", "ADR-030"]
---

# ARCH-001: Architecture Overview

Scope: AML-KYC-Agent v0.3.0 (Phases 1-3, built) plus the Phase 4 alert investigator (FR-009/FR-010/FR-011, proposed, not built). Synthetic data only (NFR-006).

ADR note: decisions are now recorded in `docs/design/adrs/` (ADR-001..016 accepted, retroactive; ADR-017..027 accepted at the Design sign-off; ADR-028..030 proposed, pending sign-off). D1-D10 and R-xx labels are kept in the text; mapping: D1 -> ADR-017 (+ADR-023), D2 -> ADR-018, D3 -> ADR-019, D4 -> ADR-020, D5 -> ADR-021, D6 -> ADR-022, D7 -> ADR-024, D8 -> ADR-025, D9 -> ADR-016/017, D10 -> ADR-026, D11 (hallucination controls, FR-011) -> ADR-027. R-xx to ADR: R-01..R-11 -> ADR-001..011 in order; R-12 loopback API -> ADR-012, R-13 synthetic data -> ADR-015, R-14 hard-coded config -> ADR-013, R-15 idempotent migrations -> ADR-014, R-16 -> ADR-016.

v1.1 delta (2026-11-23, NFR-008 v1.1, FR-010 v1.2): network segmentation (section 1a), self-hosted model server `llm` and `LLM_MODE=local`, `DATA_CLASSIFICATION` gate, dedicated OFAC fetch service. New: B16-B18, RR-23, RR-24; revised: B8, B9, B12, B15, RR-1, RR-20. All delta items are PHASE 4 (proposed design, not built). Decisions needing a proposed ADR are listed in section 10.

Status legend used below: BUILT = in the repo now; PHASE 4 = proposed design, implemented only if signed off; DEFERRED = recorded residual risk.

## 1. Component Diagram

```
                    (synthetic producers)                      HTTP client (loopback only)
                    pipeline.py seed/generate                           |
                    pipeline.py:29-47 produce()                         v  127.0.0.1:8000 (compose.yaml:61)
                              |                                   +-----------+
                              | key=account (pipeline.py:44)      |  api.py   |  FastAPI/uvicorn
                              v                                   +-----------+
                 +-----------------------------+                   |  |  |  imports: pipeline.DSN (api.py:5),
                 | kafka (Redpanda v24.3.10)   |                   |  |  |  kyc, watchlist (api.py:27-29)
                 | topics: transactions(1p)    |                   |  |  +--> kyc.py --> watchlist.py --> rapidfuzz,
                 |         alerts(1p)          |                   |  |        (Application, review)      defusedxml
                 | PLAINTEXT, no auth          |                   |  |
                 +-----------------------------+                   |  |  reads audit; writes kyc_applications+audit
                   |   ^         |        |                        |  |
 transactions      |   | alerts  |        | alerts (PHASE 4)       |  |
                   v   |  (Quix) |        v                        v  v
  +------------+  +-----------+  |   +------------------+    +------------------------------+
  | ingest     |  | scorer    |  |   | investigator     |    |  postgres 16 + pgvector      |
  | pipeline.  |  | scoring.py|--+   | investigator.py  |    |  tables: cases, transactions,|
  | py:62-83   |  | Quix app  |      | (PHASE 4)        |    |  audit, kyc_applications,    |
  +------------+  +-----------+      +------------------+    |  screened_counterparties     |
     |   uses        |  |  |   uses      |        |          |  roles: postgres (superuser),|
     |   pipeline.   |  |  |   rules.assess        |          |   aml_worker (SELECT/INSERT),|
     |   record_     |  |  +-> rules.py (pure)     |          |   aml_investigator (PHASE 4) |
     |   transaction |  +----> kyc.payment_screen   |          +------------------------------+
     |               |           -> watchlist.active|              ^   ^   ^   ^
     |               v                              |              |   |   |   |
     |        +-------------+                       |  SELECT tx + view investigator_audit, INSERT audit (aml_investigator)
     |        | redis 7     |                       |              |   |   |   |
     |        | Lua velocity|                       +--------------+   |   |   |
     |        | no password |                                          |   |   |
     |        +-------------+                          ingest/scorer/api share role aml_worker
     |                                                 via hard-coded DSN (pipeline.py:10)
     +-------------------------------------------------------------------+

  investigator --(HTTPS, LLM_MODE=anthropic only)--> Anthropic API   (PHASE 4; stub mode = no network)
  investigator.py --imports--> llm.py, grounding.py (grounding.py: pure checks; PHASE 4)
  eval_investigator.py (opt-in, dev host) --> tests/eval/scenarios.json; --HTTPS (LLM_MODE=anthropic)--> Anthropic API; writes eval-report.json
  migrate (postgres:16 + psql, superuser) --> sql/002, 003, 004 every start (initdb mounts only 001)        compose.yaml:34-41
  topic (rpk one-shot) --> creates transactions, alerts with -p 1                 compose.yaml:11-16
  latency.py (NFR-001 gate client, run on demand) --produce--> transactions (latency.py:19,37)
                                                  <--consume-- alerts, random group.id, no commit (latency.py:38-43)
                                                  imports pipeline.BROKER, TOPIC, event (latency.py:8)
  scorer, api mount ./watchlists read-only; SDN_FILE selects the XML             compose.yaml:46,57
  watchlist.refresh() --> HTTPS --> sanctionslistservice.ofac.treas.gov           watchlist.py:16,105-116 (PHASE 4: run only in `watchlist-fetch`, section 1a)
  investigator --(HTTP, LOCAL_LLM_URL, LLM_MODE=local)--> llm (self-hosted Ollama, internal only, no host port)   (PHASE 4)
```

### 1a. Network topology (PHASE 4, NFR-008.1-NFR-008.3)

Three Compose networks. `internal` is declared `internal: true` (no gateway, no route out); `ingress` and `egress` are ordinary bridge networks.

```
 HOST ---127.0.0.1:8000---> [ingress net, non-internal] --- api ---+
                                                                   |   (api also on internal)
 +================== internal net (internal: true, NO route out) ===+=============================+
 |  postgres   redis   kafka(Redpanda)   topic   migrate   scorer   ingest   investigator   llm     |
 |  (api)                                                                  |           ^           |
 |                                                                         +--LOCAL_LLM_URL--+     |
 +==========================================================================|======================+
                                                                            | only with the override
                                                                            | file (anthropic mode)
 [egress net, non-internal] <---------------------------------------------+
     ^   ^
     |   +-- investigator (compose.anthropic.yaml override only) --HTTPS--> api.anthropic.com (synthetic only)
     +------ watchlist-fetch (profile `fetch`; no secrets; NOT on internal) --HTTPS GET--> OFAC
                  writes ./watchlists only  ==(bind mount, ro)==> api, scorer
```

Membership (target `compose.yaml`; reviewed by `docker compose config`, NFR-008 AC-2/AC-7/AC-8):

| Service | internal | ingress | egress | Host port | Notes |
|---------|:--------:|:-------:|:------:|-----------|-------|
| postgres, redis, kafka, topic, migrate, scorer, ingest | yes | no | no | none | `postgres`, `redis`, `kafka` never publish (NFR-008.2) |
| api | yes | yes | no | `127.0.0.1:8000` | ingress network exists only to publish the loopback port (NFR-008.3(e)) |
| investigator | yes | no | only with override | none | default (stub/local) has no outbound route |
| llm (Ollama) | yes | no | no | none | weights baked into the image or a local volume, never pulled at runtime (the control that prevents a runtime pull is the `internal: true` network, which has no route out; `OLLAMA_NOPRUNE` only stops blob pruning and is not a pull control; no `ollama pull` at start); reached at `LOCAL_LLM_URL=http://llm:11434` |
| watchlist-fetch | no | no | yes | none | Compose `profiles: ["fetch"]` so it never starts by default; no secrets; no DB connection; only write mount `./watchlists` |

Decisions in this topology:
- Anthropic egress is enabled by a Compose override file, `compose.anthropic.yaml`, which adds `investigator` to `egress`, not by a profile. Reason: a profile can only add whole services, not change another service's networks; and a separate file makes the egress opt-in explicit on the command line (`docker compose -f compose.yaml -f compose.anthropic.yaml up`) and diffable in review. The base `compose.yaml` therefore always satisfies NFR-008 AC-1/AC-7.
- Defense in depth for anthropic mode: the `DATA_CLASSIFICATION=synthetic` startup gate (FR-010.6, data-flow section 2a) is the control that decides whether customer data can go out; the override file is the control that decides whether a route exists. Neither alone is sufficient: the file alone leaves a route open, the env var alone leaves a dormant misconfiguration reachable.
- Docker networks cannot restrict egress by hostname. In anthropic mode the investigator, which holds DB access and evidence, has a route to the whole internet. An egress proxy allow-listing `api.anthropic.com` would close this, but adds a new service, TLS interception or CONNECT filtering, and a new trust component for a mode that is only permitted on synthetic data. Decision: not built, recorded as RR-24 (host-unrestricted egress), mitigated by the synthetic gate and the opt-in override. If real data is ever in scope, `anthropic` mode is not allowed at all (NFR-008.3(a)), so the proxy is not on the path to real-data use.
- Redpanda dev-container telemetry: Redpanda (dev-container mode) tries to report usage to an external endpoint. The `internal` network blocks it; recommended to also disable it explicitly (add `--set redpanda.enable_usage_stats=false` or the equivalent rpk/`redpanda.yaml` setting to the `kafka` command in `compose.yaml`) so the attempt does not log connection errors and the intent is in config rather than implied by network state. Verify the exact flag against the pinned Redpanda v24.3.10 at implementation (CS owner).
- Startup-order consequence: `migrate`, `topic` and `kafka` no longer have internet; image pulls happen on the Docker engine (NFR-008.3(d)), not inside containers.

External dependencies: Redpanda, PostgreSQL+pgvector (extension installed, unused: sql/001-foundations.sql:1), Redis, Quix Streams 3.15.0, confluent-kafka, psycopg 3.2.6, FastAPI/uvicorn, pydantic 2, RapidFuzz, defusedxml 0.7.1 (requirements.txt:1-10). PHASE 4 adds the `anthropic` SDK (pinned exactly, D6) and the Ollama image for the `llm` service (pinned by digest, ADR-029, DI-011).

## 2. Layer Architecture

Derived from the import graph: `api -> {pipeline, kyc, watchlist}`; `latency -> pipeline` (BROKER, TOPIC, event); `scoring -> {pipeline, rules, kyc}`; `kyc -> watchlist`; `rules` imports nothing; `pipeline` imports no project module. PHASE 4 dependency direction (W29): `investigator.py` imports `llm.py` and `grounding.py`; `grounding.py` imports only pydantic, `re` and `watchlist.normalize`; `llm.py` imports neither; grounding enters the retry loop as an injected validate callback.

New Phase 4 modules: `grounding.py` (pure grounding/consistency checks), `eval_investigator.py` (opt-in eval script), `tests/eval/scenarios.json` (synthetic evaluation scenarios).

| Layer | Modules | Responsibility | Depends on |
|-------|---------|----------------|-----------|
| L1 Interface / entrypoints | `api.py` (HTTP), `pipeline.py` CLI (`ingest\|seed\|benchmark\|generate`, pipeline.py:108-123), `scoring.py:run`, `latency.py` (NFR-001 latency-gate client: producer to `transactions` plus consumer of `alerts` under a random group, latency.py:37-43), PHASE 4 `investigator.py`, opt-in `eval_investigator.py` | Accept external input, wire dependencies | L2-L4 |
| L2 Orchestration | `scoring.py` `score()` (scoring.py:30-51); PHASE 4 investigator per-message loop (D1) | One DB transaction per message; ordering of steps | L3, L4 |
| L3 Domain logic | `rules.py:assess` (pure), `kyc.py` (`review`, `payment_screen`, `Application`), PHASE 4 evidence builder/validator, `grounding.py` (pure) | Decisions; no I/O except `payment_screen` DB write | L4 |
| L4 Infrastructure / shared | `pipeline.py` constants + `record_transaction` (pipeline.py:8-10,50-59), `watchlist.py` (parse, normalize, screen, cache), PHASE 4 LLM interface (Stub, Anthropic) | Config, persistence primitive, watchlist snapshot | external systems |
| L5 Data | `sql/*.sql`, Redis Lua `VELOCITY` (scoring.py:15-22) | Invariants (unique indexes, grants), velocity windows | - |

Smell recorded, not fixed: `pipeline.py` serves as both config module and Phase 1 consumer, so `api.py` imports the ingest module for `DSN` (R-14, hard-coded config). `api.py:27-29` has mid-file imports.

## 3. Caching / State Architecture

| State | Location | Lifetime / rule |
|-------|----------|-----------------|
| Watchlist snapshot | `watchlist.cached` `lru_cache(maxsize=2)` keyed (path, mtime_ns, size) (watchlist.py:94-102) | Per process. A changed file produces a new key; otherwise restart to change snapshot (CLAUDE.md). Version = SHA-256 of bytes (watchlist.py:91) |
| Velocity windows | Redis sorted set `velocity:<account>`, Lua script (scoring.py:15-22) | Event-time score; `ZADD NX` makes retries count once; trimmed to 48 h behind latest; `EXPIRE 172800`. AOF on (compose.yaml:32). Derived state; DB is authoritative |
| Screening de-dup | `screened_counterparties` PK (account, name_key, snapshot) (sql/003-kyc.sql:6-9; kyc.py:85-87) | Counterparty screened once per account+name+snapshot |
| Score replay cache | `audit` row `scored.v1`; reused when present (scoring.py:34-37) | Permanent |
| Kafka offsets | Consumer groups `aml-ingest-v1`, `aml-scorer-v1`, PHASE 4 `aml-investigator-v1` | Committed after DB commit (pipeline.py:75-81); investigator the same (D1) |
| Audit / system of record | `audit` table | Permanent (D8: retained at least 5 years, no deletion path) |
| PHASE 4 stored model I/O | `audit.inputs` of `investigation.*.v1` rows (exact payload + SHA-256, D4) | Permanent, same as audit |

No HTTP-level or LLM-response cache is designed.

## 4. Concurrency Model

- Ingest: synchronous `confluent_kafka.Consumer`, batches of 100, one DB transaction per batch, `consumer.commit(asynchronous=False)` after commit (pipeline.py:72-81).
- Scorer: Quix Streams dataframe, one message at a time per partition; one DB transaction per message (scoring.py:31). Account-keyed single-partition input serializes per-account updates (scoring.py:13 comment; R-02). Single-partition is a deliberate throughput ceiling; NFR-001 gates (50 rows/s, p95 < 500 ms) are the evidence it is adequate.
- API: uvicorn; sync handlers run in the thread pool; one new `psycopg.connect(DSN)` per request (api.py:12,22,35); no pooling.
- Replay / double-delivery safety comes from DB unique indexes, not locking (sql/002-scoring.sql:3-4).
- PHASE 4 investigator (D1, D9): single synchronous consumer process, one alert at a time, outside the scorer path, so NFR-001 gates are unaffected. Model call occurs OUTSIDE any DB transaction; `max.poll.interval.ms >= LLM_TIMEOUT_SECONDS x LLM_MAX_ATTEMPTS + backoff + 60 s`. Startup asserts `alerts` has 1 partition. W23 is CLOSED for integrity: the combined `audit_investigation_alert_once` index plus the drafted-once index make drafted and skipped mutually exclusive per `alert_key` in the database, regardless of consumer count. The single-partition assertion now only bounds duplicate model calls (RR-14). Edge case, by design: a forged or early origin-keyed `not_alerted` skip can coexist with a later genuine draft for the same transaction, because the two rows have different `alert_key`s.
- PHASE 4 integrity vs efficiency (corrected per coordinator): sql/004 creates (a) a unique index on `audit(transaction_id) WHERE action='investigation.drafted.v1'` and (b) one unique index on `((inputs->>'alert_key')) WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1')`; drafted rows carry `alert_key = transaction_id`. A drafted and a skipped row for the same alert key therefore cannot both exist: the database enforces mutual exclusion and at-most-one-draft. The advisory lock (`pg_advisory_xact_lock(hashtext(alert_key))`) and pre-check exist only to avoid duplicate model calls, not to provide integrity. Note the lock is transaction-scoped and released at the step-2 commit, so it narrows but does not close the duplicate-model-call window if a second consumer ever ran; the single-partition assertion and single consumer are what keep that window shut. `INSERT ... ON CONFLICT DO NOTHING` (no conflict target, so it covers both indexes) is the integrity backstop; the first writer wins.

## 5. Design Patterns

| Pattern | Where |
|---------|-------|
| Append-only event log / system of record | `audit` table, versioned `action` strings (sql/001-foundations.sql:15-19; NFR-004) |
| Idempotent receiver | `INSERT ... ON CONFLICT DO NOTHING` + partial unique indexes (pipeline.py:52-54; sql/002-scoring.sql:3-4) |
| Commit-after-persist (at-least-once + idempotency) | pipeline.py:75-81 |
| Replay check / memoized decision | scoring.py:34-37 |
| Pure function core | `rules.assess` (rules.py:2-31) |
| Pipeline / stream processing | Quix dataframe `apply -> filter -> to_topic` (scoring.py:52-54) |
| Lua script as atomic unit | scoring.py:15-22 |
| Snapshot versioning by content hash | watchlist.py:91 |
| Memoization | `lru_cache` (watchlist.py:94) |
| Validation at boundary (parse, don't validate later) | pydantic `Application`, `Text` 1-256 chars, list caps (kyc.py:9-36); PHASE 4 strict output model (D3) |
| Idempotent API (409 on payload conflict) | api.py:37-45 |
| Recommend-only / human-in-the-loop | kyc.py:51-90 record only; NFR-005; D9 |
| Strategy (PHASE 4) | LLM interface with Stub and Anthropic implementations (D6) |
| Fail-fast configuration (PHASE 4) | missing `INVESTIGATOR_DB_PASSWORD_FILE`, unknown `LLM_MODE`, missing key in anthropic mode |
| Idempotent migrations | `IF NOT EXISTS`, re-run each start (compose.yaml:34-41; sql/002-scoring.sql) |

## 6. Trust Boundaries & Threats (STRIDE-lite)

Method: Microsoft SDL design-time threat modeling, STRIDE-lite (S spoofing, T tampering, R repudiation, I information disclosure, D denial of service, E elevation of privilege). Rows exist only for boundaries present in the code or in the Phase 4 design. Status tags: BUILT, PHASE 4, DEFERRED.

### 6.1 Trust boundary diagram

```
 BUILT today: one flat compose network. PHASE 4 target: internal / ingress / egress split (section 1a);
 the diagram below shows boundaries, not network membership.
 +-- UNTRUSTED -----------------+      +-- compose network (flat, one trust zone today) ---------------------------+
 | HTTP client (loopback)   --B1-----> | api -----B6--+  (B18: api on ingress net)                                |
 | OFAC site (HTTPS)  --B9--> watchlist.refresh() (PHASE 4: watchlist-fetch, B17)                                  |
 | Synthetic producer (any    --B2--> kafka --B3--> ingest/scorer --B4--> postgres <--B5-- scorer/api (aml_worker)|
 |  network peer can publish)   |   |                 |                         ^                                  |
 | Env / compose / secrets files --B8--> all services  +--B7--> redis           |                                  |
 +------------------------------+   |  alerts --B10--> investigator --B11--(aml_investigator)--+                 |
                                    +----------------------------+--B12--HTTPS--> Anthropic API (3rd party, synthetic only) |
                                                                  +--B16--HTTP--> llm (in-deployment model server)  |
                                                                  +--B13--> model OUTPUT (untrusted text) -> audit |
 Superuser path: migrate / postgres init --B14--> postgres (owner can bypass grants)                              |
 +--------------------------------------------------------------------------------------------------------------+
```

### 6.2 Boundary table

| # | Boundary | What crosses it (source ref) | Threats | Mitigation |
|---|----------|------------------------------|---------|-----------|
| B1 | HTTP client -> api (`GET /scores`, `GET /alerts`, `POST /onboarding`) | Path UUID (api.py:11), JSON `Application` incl. names, DOB, id_number, address (api.py:33; kyc.py:12-36); responses return audit `inputs` (api.py:17,24) | S, T, R, I, D, E | Loopback-only publish (compose.yaml:61; NFR-003); pydantic validation with length and list caps (kyc.py:9,28,35-36); parameterized SQL (api.py:13,23,37); 409 on payload conflict (api.py:43-44). ACCEPTED RISK / DEFERRED: no authN/Z, no access log (ASVS V2/V4/V7), container binds 0.0.0.0 (compose.yaml:60) behind the loopback publish; single-user synthetic demo (NFR-006) |
| B2 | Producer -> Kafka `transactions` | JSON transaction, key=account (pipeline.py:44; also produced by `latency.py:19`) | S, T, D | Single-purpose synthetic producer; every consumer write is idempotent and DB-constrained (CHECK on amount/direction, sql/001-foundations.sql:10-11). DEFERRED: PLAINTEXT, no SASL/ACL (SC-8/IA); flat network, only API published, so no host exposure |
| B3 | Kafka -> ingest / scorer (deserialization) | `json.loads(msg.value())` with no schema check (pipeline.py:79); Quix json deserializer (scoring.py:52) | T, D | DB constraints reject bad rows (txn rolls back). DEFERRED: a malformed message crash-loops the consumer (`restart: on-failure`, compose.yaml:68,52); recorded residual risk |
| B4 | Services -> PostgreSQL as `aml_worker` | Transactions, audit, KYC PII, screening results (pipeline.py:52-59; api.py:37-48; kyc.py:85-90) | S, T, R, I, E | Role has SELECT/INSERT only (sql/001-foundations.sql:21-23; sql/003-kyc.sql:10), no INSERT on `cases`; partial unique indexes (sql/002-scoring.sql:3-4); `audit` is append-only by grants (NFR-003). Residual: one shared role and hard-coded DSN for three services (pipeline.py:10) so audit `actor` is self-asserted; PHASE 4 adds a two-way BEFORE INSERT guard (B11, B14) so `aml_worker` can no longer forge investigator rows |
| B5 | Postgres connection transport / storage | Plaintext TCP inside compose; `pg-data`, `kafka-data`, `redis-data` volumes (volume mounts compose.yaml:5, :23, :33; declarations compose.yaml:69-72) | I, T | DEFERRED: TLS (SC-8) and at-rest encryption (SC-28) for all three volumes (Postgres rows, Kafka message bodies, Redis AOF); PII in `kyc_applications` untokenized. ACCEPTED RISK: synthetic data, no host port published |
| B6 | api -> kyc/watchlist (in-process) | Applicant strings into `normalize`/RapidFuzz (watchlist.py:20-23,47) | D | Strings capped at 256 chars, owners recursion bounded by list caps (kyc.py:9,28,35-36); `Text` rejects empty |
| B7 | scorer -> Redis | Account id, event-time score, transaction id via Lua (scoring.py:39) | T, D, I | Redis not published; velocity is derived state, DB authoritative. DEFERRED: no password, no TLS (IA-5/SC-8) |
| B8 | Config/secrets -> services | Hard-coded DSN/BROKER/TOPIC (pipeline.py:8-10); `SDN_FILE` env (watchlist.py:100); compose credentials (compose.yaml:21,37); PHASE 4 `INVESTIGATOR_DB_PASSWORD_FILE` and `ANTHROPIC_API_KEY_FILE` secret files | I, E | BUILT: demo credentials only, synthetic data (NFR-006). PHASE 4: compose secret files (D5), no fallback to `aml_worker` DSN (D2), key read only when `LLM_MODE=anthropic` AND `DATA_CLASSIFICATION=synthetic` (gate runs first; unset or any other value exits non-zero before the key file is opened or any socket is created, FR-010.6; `DATA_CLASSIFICATION` is also validated in every mode), never logged or audited, `.gitignore` adds `secrets/*` and `!secrets/demo/` (plus `.jetro/` and `.claude-flow/`), so the committed synthetic demo secrets under `secrets/demo/` stay tracked and real secrets are ignored; the API key comes from `ANTHROPIC_API_KEY_FILE`, env only as a dev fallback. PHASE 4 (D10): Dockerfile creates a non-root user (`useradd --system --uid 10001 app`, `USER app`) for all services (Dockerfile currently has no `USER`, Dockerfile:1-8) |
| B8a | Investigator DB password path (secret file -> migrate, investigator) | One file, `/run/secrets/investigator_db_password`: `migrate` reads it (psql `\set` from `cat`, `set_config(..., true)`, `ALTER ROLE` on every start so the role stays in sync) and the investigator builds its DSN from the same file with no fallback | I, E | PHASE 4: single source file, no fallback to the `aml_worker` DSN (D2, D5); demo value under `secrets/demo/` is synthetic, real files gitignored. Residual RR-15: psql error context and server logs can echo the statement containing the password |
| B9 | OFAC download -> watchlist | 128 MiB-capped HTTPS body, XML (watchlist.py:16,107-110) | T, D, S | `defusedxml` parse (watchlist.py:13), size cap, `parse()` completeness check against Record_Count (watchlist.py:88-90), atomic `os.replace` (watchlist.py:112-115), SHA-256 version recorded in every screening (watchlist.py:91). Manual command, watchlists mount read-only to api/scorer (compose.yaml:46,57). PHASE 4: runs only in the one-shot `watchlist-fetch` service (see B17). Residual RR-18: no signature check of the list beyond TLS |
| B10 | Kafka `alerts` -> investigator | Alert JSON `{transaction_id, case_id, run_id, version, score, alert, rules}`; no account (CLAUDE.md; scoring.py:53) | S, T, D | PHASE 4: the alert message is only a trigger. The investigator acts only when an `alerted.v1` row exists for the transaction (read via `investigator_audit`, which now includes `alerted.v1`); evidence comes from the DB, never from the Kafka payload; account re-read from DB. `unknown_transaction` / `not_alerted` skips are keyed by Kafka origin (`alerts:<partition>:<offset>`), so a forged alert cannot occupy a real alert's `alert_key` slot (and thus cannot suppress a later genuine investigation). Malformed alerts recorded as skipped, offset committed, no crash-loop (FR-009.7); per-alert caps. `latency.py:28` also consumes `alerts` with an unvalidated `json.loads`; it is a CI benchmark client on the same compose network, covered by the same residual. Residual RR-19: Kafka is unauthenticated, so forged alerts still create noise skip rows (bounded: one row per forged message, no model call). `case_id` handling (W2): skipped rows for `malformed_alert`, `unknown_transaction` and `not_alerted` have `case_id` NULL; all other rows take `case_id` from the DB `scored.v1` row, never from the Kafka payload |
| B11 | investigator -> PostgreSQL as `aml_investigator` | Reads `transactions` and the view `investigator_audit`; inserts `investigation.*.v1` rows (D2) | T, R, I, E | PHASE 4: SELECT on `transactions` and on view `investigator_audit` only (sql/004; columns event_id, recorded_at, actor, action, case_id, transaction_id, inputs, model_version, prompt_version, filtered to actions `scored.v1`, `alerted.v1`, `payment.screened.v1`, `investigation.drafted.v1`, `investigation.skipped.v1`); NO SELECT on the `audit` table, `kyc_applications`, `screened_counterparties` or `cases`, so onboarding PII (`kyc.reviewed.v1`, `onboarding.screened.v1`, api.py:46-48) is excluded at the database level; INSERT on `audit` plus USAGE on `audit_event_id_seq`. Because the role has no SELECT on `audit`, inserts must not use `RETURNING`; `ON CONFLICT DO NOTHING` needs no read privilege. BEFORE INSERT guard is two-way: (1) `aml_investigator` may write only actor `investigator-v1` with action `investigation.drafted.v1` or `investigation.skipped.v1`; (2) any `investigation.*` action or actor `investigator-v1` requires `current_user='aml_investigator'`, so forging by `aml_worker` is blocked. This reverse guard is backed by NFR-003 (amended): no other role can write `investigation.*` rows or actor `investigator-v1`; mutual exclusion and at-most-one-draft by unique indexes (a),(b) in sql/004; ON CONFLICT DO NOTHING. Residual: the view hides rows but a view owner or superuser can redefine it (RR-5) |
| B12 | investigator -> Anthropic API (third party) | Evidence JSON in a delimited block; HTTPS; API key (D3,D4,D5) | I, T, D, S | PHASE 4 only when `LLM_MODE=anthropic` AND `DATA_CLASSIFICATION=synthetic` (startup gate before key read or network, FR-010.6, NFR-008.3(a)); otherwise exit non-zero. Default modes `stub`/`local` have no outbound route (internal network, NFR-008.1); the route exists only when the opt-in `compose.anthropic.yaml` override puts `investigator` on `egress`. Egress is NOT host-restricted (Docker networks cannot filter by host): residual RR-24. Audit rows carry `inputs.data_classification`. Deny-by-default field allow-list; account aliased `SUBJECT_ACCOUNT`; no KYC data; strings capped 256 chars, control chars stripped; history capped 50 tx/30 days; rule evidence capped at 50 ids per rule, longer lists truncated and flagged `evidence_truncated`, never rejected (LLM02, GLBA, LLM10). Timeout, 3 attempts, `max_retries=0` in SDK (LLM10). Exact payload + SHA-256 stored in `inputs`. Provider exceptions sanitized to type+status. Residual RR-20: no DPA / zero-data-retention review for the model provider; applies only to synthetic deployments, where it is acceptable because data is synthetic (a deployment with real data cannot start anthropic mode at all). Opt-in eval path: `eval_investigator.py` runs from a dev host to the Anthropic API (HTTPS), sends synthetic scenarios only (`tests/eval/scenarios.json`), requires `LLM_MODE=anthropic` and `DATA_CLASSIFICATION=synthetic` (exits non-zero otherwise, FR-010.6 AC-5), writes a local `eval-report.json`, and never writes the production audit. Residual: the dev host holds the API key and the report is an unprotected local file; acceptable because scenarios are synthetic |
| B13 | Model output -> audit store / readers (all modes: stub, local, anthropic; B16 output is equally untrusted) | `summary`, `recommendation`, `cited_transaction_ids`, `findings` (D3, FR-011) | T, I, E (LLM09) | PHASE 4: strict pydantic (`extra=forbid`), summary <= 2,000 chars, enum recommendation, citations subset of evidence ids; invalid output retried then skipped `model_failure` (LLM05); no tools or function calling, no Kafka publish, no `cases` write (LLM06, NFR-005); summary stored as untrusted text and never executed or rendered as HTML. Prompt injection via attacker-influenced `counterparty` text (LLM01): delimited `<evidence>` block, "untrusted data" system prompt, capped strings, no tool surface, so the worst outcome is a misleading summary, which a human analyst must weigh. Hallucination controls (FR-011, ADR-027; LLM09 misinformation / overreliance): claim-level findings; deterministic grounding checks of amounts ($-prefixed amounts matched whole, never truncated, compared in integer cents; a malformed $-amount fails), counterparties, rule names and sanctions wording against the evidence, then retry, then skip `grounding_failure`; `consistency_warning` is informational and never overrides the recommendation; every drafted row carries `ai_generated`, `requires_human_review` and grounding labels; evaluation set (stub in CI, plus opt-in real-model run that reports metrics to a local report only). Residual RR-21: see section 8 (unchecked: amounts without "$", unquoted counterparty names, sanctions paraphrases outside the term list; semantic misstatements rely on human review). Also residual: analyst disposition not recorded (SR 11-7) |
| B14 | Superuser / migrate -> audit | `migrate` runs as `postgres` (compose.yaml:36-39) | T, R, E | PHASE 4: BEFORE UPDATE OR DELETE and BEFORE TRUNCATE triggers raise for every role including the owner (D7). Residual: a superuser can still `DROP TRIGGER`/disable it, and there is no hash chain (AU-9); migrate runs as superuser; initdb mounts ONLY `sql/001-foundations.sql` (compose.yaml:24 to change), and `migrate` runs 002-004 on every start (compose.yaml:34-41), so 002-004 are re-run idempotently and never at initdb |
| B15 | Python package supply chain / container images | `requirements.txt`, base images (Dockerfile:1-4; compose.yaml:3,18) | T | Exact pins for psycopg, quixstreams, defusedxml (requirements.txt:2,3,9; NFR-003); PHASE 4 pins `anthropic` exactly. The `llm` image and its baked-in weights are a new supply-chain input (model file integrity); pin the image by digest (ADR-029, DI-011) and record the weights digest at build, never download at runtime (NFR-008.1). Residual RR-22: version ranges for the rest, images tagged not digest-pinned, no SCA/SBOM in CI, no weights signature check |
| B19 | kafka (Redpanda) -> vendor usage/telemetry endpoint (outbound attempt) | Redpanda usage statistics, no customer data intended | I, D | PHASE 4. Blocked by the `internal` network (no route out). Explicit disable in the `kafka` command, verified against the pinned image in Develop (ADR-028), so the intent is in config and not only implied by network state |
| B16 | investigator -> `llm` model server (internal HTTP, `LOCAL_LLM_URL`; response back) | Same minimized, aliased evidence payload as B12 (D3, D4) out; model text back. Plain HTTP, no auth, on `internal` only | I, T, D, S | PHASE 4. No route outside the deployment: both ends on `internal` (NFR-008.1, AC-6), so evidence never leaves; `LOCAL_LLM_URL` host is not validated, network isolation is the control (FR-010.5 AC-5). Output handling is identical to B13 (strict pydantic, grounding, no tools, FR-011), because a local model is no more trustworthy than a hosted one. Same timeout, attempts, backoff (D6); unreachable server yields `model_failure` skip (FR-010.5 AC-4). `llm` has no secrets, no DB access, no host port. Residual: no TLS/auth on the hop (RR-1), same-network peers can call `llm` or answer as it (spoof), bounded to noise or a misleading draft that B13 checks catch or a human weighs; model quality is lower than hosted, which the FR-011 evaluation set measures |
| B17 | OFAC site -> `watchlist-fetch` -> `./watchlists` -> api/scorer (egress net) | Public SDN XML in (HTTP GET, HTTPS, 128 MiB cap); NO customer data out; file written to `./watchlists` (watchlist.py:16,105-116) | T, D, S, E | PHASE 4. Dedicated one-shot service, Compose profile `fetch` (never starts by default), only on `egress`, NOT on `internal`, no secrets, no DB connection, write mount only `./watchlists` (NFR-008.3(b), AC-8). Parse and integrity as B9 (defusedxml, size cap, Record_Count, atomic `os.replace`, SHA-256). api and scorer mount `./watchlists` read-only and cache by (path, mtime, size) so a new file is a new snapshot. Residual: RR-18 (no signature check); the fetch container could write any file in `./watchlists` if compromised, bounded because the mount is the only write path and consumers parse with defusedxml and fail on an incomplete list |
| B18 | Host loopback -> `ingress` network -> api (and api's technical outbound route) | Inbound HTTP on `127.0.0.1:8000` (B1); the `ingress` network is non-internal, so `api` has a Docker gateway route out | I, E (exfil path), D | PHASE 4 NFR-008.3(e). `api` is on `internal` and `ingress` only; code makes no outbound calls (NFR-008 AC-5 grep for `urllib`, `requests`, `httpx`, `socket`, `anthropic`; api imports pipeline, kyc, watchlist, none of which open sockets except to postgres/kafka/redis on `internal`). `api` runs as non-root `app` (D10), holds only the `aml_worker` DSN, no secrets. Residual RR-23: a code or dependency compromise of `api` could use the route; no network control prevents it. Option not taken: an `ingress` proxy container (publishing the port) in front of an internal-only `api`, which would remove the route at the cost of one extra hop and service |

No boundary exists for card data, so PCI DSS is N/A.

## 7. Security Standards Mapping

Status values: IMPLEMENTED (built today), PHASE 4 (implemented if the Phase 4 design is signed off), DEFERRED (recorded residual risk, section 8). This is a synthetic-data demo; "implemented" means the control exists in code, not that the system is certified or production-ready. PCI DSS: N/A, no cardholder data.

| Standard / control | Requirement (short) | Control in this design | Status |
|--------------------|--------------------|------------------------|--------|
| FFIEC BSA/AML Exam Manual (monitoring, model use) | Documented monitoring rules, human review of alerts, auditable decisions | `rules.py` documented rules marked illustrative (rules.py:1); every decision is an `audit` row with evidence (NFR-004); systems recommend only (NFR-005, D9) | IMPLEMENTED; analyst disposition recording DEFERRED; no SAR filing in scope |
| 31 CFR 1010.430 | Retain records 5 years | Audit rows retained at least 5 years, no deletion path, UPDATE/DELETE/TRUNCATE blocked by trigger (D7, D8). Conflict with privacy deletion documented | PHASE 4 (design); backup/retention operations not built (volumes only) |
| NIST 800-53 AU-2 | Define auditable events | Versioned actions for every decision (NFR-004); Phase 4 adds `investigation.drafted.v1`, `investigation.skipped.v1` | IMPLEMENTED + PHASE 4; API access events not logged (DEFERRED, ASVS V7) |
| NIST AU-3 | Audit record content | `event_id`, `recorded_at`, `actor`, `action`, `case_id`, `transaction_id`, `inputs`, `model_version`, `prompt_version` (sql/001-foundations.sql:15-19); Kafka origin on ingest rows (pipeline.py:80) | IMPLEMENTED; actor is self-asserted by shared role for existing services (B4), enforced for investigator by the two-way BEFORE INSERT guard, which also blocks forging of `investigator-v1`/`investigation.*` by `aml_worker` (D2) |
| NIST AU-9 | Protect audit information | Append-only grants (sql/001-foundations.sql:21-23); Phase 4 triggers block UPDATE/DELETE/TRUNCATE for all roles (D7) | grants IMPLEMENTED; triggers PHASE 4; hash chain and superuser separation DEFERRED |
| NIST AC-6 | Least privilege | `aml_worker` SELECT/INSERT only; `aml_investigator` has no SELECT on `audit` (only the filtered view `investigator_audit`), no KYC/cases access, actor/action pinned by trigger, no fallback DSN (D2); investigator holds the only model key (D5); non-root containers (D10) | partial IMPLEMENTED; PHASE 4 for investigator and D10; shared `aml_worker` role for the three existing services DEFERRED |
| NIST SC-8 | Transmission confidentiality/integrity | Loopback-only API publish; internal services unpublished (compose.yaml:61) | internal TLS/SASL DEFERRED. Provider HTTPS in PHASE 4 |
| NIST SC-28 | Protection at rest | None | DEFERRED (at-rest encryption, PII tokenization) |
| NIST IA-5 | Authenticator management | Compose secret files for DB password and model key, env fallback for dev, never logged (D5); `.gitignore` additions | PHASE 4; demo passwords in compose.yaml:21,37 and pipeline.py:10 remain (accepted: synthetic) |
| OWASP ASVS L2 | V5 input validation, V8 data protection, V14 config, V2/V4 authN/Z, V7 logging | V5: pydantic caps (kyc.py:9-36), parameterized SQL; V8: minimization (D4); V14: pinned deps, fail-fast config | V5 IMPLEMENTED; V2/V4/V7 DEFERRED (no API authN/Z, no access log); V9 communications DEFERRED. Not an L2 claim |
| OWASP LLM01 Prompt Injection | Treat inputs as data | Delimited `<evidence>` JSON block, untrusted-data system prompt, string caps, control chars stripped, no tools (D3) | PHASE 4 |
| OWASP LLM02 Sensitive Info Disclosure | Minimize data to model | Deny-by-default allow-list, account alias, no KYC data; the role cannot read KYC tables or onboarding audit rows (view `investigator_audit`), payload + hash stored (D2, D4) | PHASE 4 |
| OWASP LLM05 Improper Output Handling | Validate and sandbox output | Strict pydantic `extra=forbid`, enum, length cap, citation subset, stored as inert text (D3) | PHASE 4 |
| OWASP LLM06 Excessive Agency | Limit capability | No tools, no Kafka publish, no `cases` write, DB role INSERT-only on audit with pinned actor/actions (D2, D9) | PHASE 4 |
| OWASP LLM09 Misinformation / Overreliance | Ground and label model output, keep humans in the loop | Claim-level findings; deterministic grounding checks (amounts, counterparties, rule names, sanctions wording), retry then skip `grounding_failure`; `consistency_warning` never overrides the recommendation; `ai_generated` / `requires_human_review` / grounding labels; evaluation set (D11, FR-011, ADR-027) | PHASE 4; semantic misstatements DEFERRED (RR-21) |
| OWASP LLM10 Unbounded Consumption | Bound cost and time | `max_tokens` 16000 with effort `low`, timeout 30 s, 3 attempts with backoff+jitter, 50-tx history cap, one alert at a time, evidence ids capped at 50 per rule (D3, D6) | PHASE 4; token budget and circuit breaker DEFERRED |
| SR 11-7 Model risk | Inventory, documentation, validation, monitoring, human oversight, change control | `model_version` (id returned by API) and `prompt_version` `investigation-prompt-v2` on every row; `prompt_sha256`, params and exact inputs stored; fixed request parameters per backend (anthropic: no `temperature`, current models reject sampling parameters; local: `temperature=0`, `format=json`, `num_predict=4096`), no fallback model, so only the recorded model writes narratives; deterministic stub for tests (D6); recommend-only (NFR-005); ongoing validation/benchmarking via the FR-011 evaluation set (stub in CI, opt-in real-model run, local report only, ADR-027) | version/reproducibility and evaluation set PHASE 4; human disposition recording, outcome analysis, dated model id (moving alias) DEFERRED |
| GLBA Safeguards Rule (16 CFR 314) | Access controls, encryption, minimization, secure development, secrets | Access: view-only, KYC-excluded investigator role (D2). Minimization: allow-list (D4). Secrets: D5. Non-root runtime (D10). Encryption: see SC-8/28 rows | partial; PHASE 4 for access and minimization; encryption and access logging DEFERRED; synthetic data only |
| PCI DSS | Card data | N/A, no card data processed | N/A |

## 8. Residual-Risk Register (deferred by design, D8)

| ID | Residual risk | Standard | Why accepted now |
|----|---------------|----------|------------------|
| RR-1 | No internal TLS/SASL (Kafka PLAINTEXT, Redis/Postgres plaintext) | SC-8 | Private compose networks (PHASE 4: `internal: true` for data-holding services), only API published, synthetic data. Hops added by the delta (investigator to `llm`) are also plaintext (B16) |
| RR-2 | No at-rest encryption (pg-data, kafka-data, redis-data volumes) | SC-28 | Same |
| RR-3 | API has no authN/Z or access logging | ASVS V2/V4/V7, AU-2 | Loopback-only demo |
| RR-4 | No analyst disposition recording | SR 11-7, FFIEC | Out of scope; recommend-only means no downstream action is taken |
| RR-5 | No audit hash chain; superuser can drop triggers | AU-9 | Triggers plus grants raise the bar; chain is a later phase |
| RR-6 | Raw PII in `kyc_applications` jsonb (api.py:37-39) | GLBA, SC-28 | Synthetic data |
| RR-7 | Existing consumers crash-loop on malformed messages (pipeline.py:79) | Availability | Out of Phase 4 scope |
| RR-8 | `LLM_MODEL` default is a moving alias, not a dated id; recorded `model_version` is what the API returned | SR 11-7 | Operator can pin a dated id via `LLM_MODEL` |
| RR-9 | No token budget or circuit breaker beyond per-alert caps. Latency/benchmark alerts (`latency.py:19`) reach the investigator, so gate runs must set `LLM_MODE=stub`; those rows land in the audit store | LLM10 | Volume bounded by alert rate; single consumer; stub mode makes no network calls |
| RR-10 | `model_failure` skip is permanent; no reprocessing path | Availability | Deliberate: skipped row dedupes redelivery (FR-009.5 AC-4) |
| RR-11 | 5-year audit retention conflicts with privacy-deletion requests | 31 CFR 1010.430 vs privacy law | Documented; BSA retention takes precedence for in-scope records |
| RR-12 | MITIGATED (proposed D2): `aml_investigator` reads audit only through view `investigator_audit`, which excludes onboarding/KYC actions. Remaining: the allow-list (D4) is still the control for which allowed-row fields reach the model | GLBA, LLM02 | View filter plus allow-list; view definition is owner-controlled (RR-5) |
| RR-13 | Shared `aml_worker` role and hard-coded DSN for ingest, scorer, api; image tags not digest-pinned; `api` binds 0.0.0.0 inside the container (behind loopback publish). Root-container part MITIGATED by D10 (non-root `app` uid 10001) | AC-6, IA-5 | Demo; Phase 4 adds a separate role only for the new service |
| RR-14 | Advisory lock does not span the model call, so concurrent consumers could duplicate a model call (not a row) | Cost only | Single partition assertion; DB indexes keep integrity |
| RR-15 | psql error context and Postgres server logs can echo the statement that sets the investigator password (B8a) | IA-5 | Synthetic demo secret; real secrets gitignored |
| RR-16 | No backups: 5-year retention relies on docker volumes only | 31 CFR 1010.430 | Demo; backup/restore is an operations phase |
| RR-17 | Investigator screening query on `inputs->>'account'` scans the growing `audit` table with no index | Performance | Low alert volume; add an expression index if latency matters |
| RR-18 | No OFAC list signature check beyond TLS (B9) | T (supply chain) | Manual refresh, defusedxml, size cap, Record_Count check, SHA-256 recorded; synthetic demo |
| RR-19 | Kafka unauthenticated: forged alerts create noise `investigation.skipped.v1` rows (B10) | S, D | Rows keyed by Kafka origin, no model call, no real alert slot occupied; broker auth is RR-1 |
| RR-20 | No DPA / zero-data-retention review for the model provider (B12). Applies only to synthetic deployments: a deployment not declared `DATA_CLASSIFICATION=synthetic` cannot run anthropic mode (FR-010.6), so this risk is never exercised with real data | GLBA, LLM02 | Synthetic data only (NFR-006) and the startup gate; a DPA review would be a precondition for ever amending NFR-008.3(a) |
| RR-25 | The `llm` container runs the Ollama image, which runs as root by default; ADR-026 covers only Dockerfile-built services (B16) | AC-6 | Run non-root if the pinned image supports it, else accepted: internal-only, no host port, no secrets, no DB access |
| RR-23 | `api` sits on the non-internal `ingress` network, so it has a technical outbound route (B18) | NFR-008.3(e), SC-7 | No outbound calls in api code (grep gate, NFR-008 AC-5), non-root, no secrets; ingress-proxy alternative rejected as extra moving part for a loopback demo |
| RR-24 | Anthropic-mode egress is not restricted to `api.anthropic.com`: the investigator, with `egress` network membership from the override file, can reach any internet host (B12) | NFR-008.3(a), SC-7 | Opt-in override file plus `DATA_CLASSIFICATION=synthetic` gate; only synthetic data exists in such a deployment; an allow-listing egress proxy is the upgrade path if the mode is kept long term |
| RR-21 | Grounding checks are partial (B13): amounts written without "$" are unchecked, as are "$" amounts using a space thousands separator ("$100 000") or no leading digit ("$.50"); unquoted counterparty names are unchecked; sanctions paraphrases outside the term list (e.g. "sanctionable", "watch list match") are unchecked; semantic misstatements (e.g. wrong characterization of intent) rely on human review | LLM09, SR 11-7 | Recommend-only (NFR-005); `requires_human_review` label; human review is the control |
| RR-22 | Version ranges, tag-only images, no SCA/SBOM in CI (B15) | Supply chain | Synthetic demo; exact pins on the security-relevant packages |

## 9. Retroactive (Accepted) Decisions Reflected Here

ADR-001 Redpanda broker (R-01). ADR-002 Account-keyed single-partition topics (R-02, compose.yaml:14). ADR-003 `audit` as system of record (R-03). ADR-004 uuid5 ids + `ON CONFLICT` + partial unique indexes (R-04). ADR-005 Offset commit after DB commit (R-05). ADR-006 Quix scorer (R-06). ADR-007 Redis Lua event-time velocity (R-07). ADR-008 Pure rules (R-08). ADR-009 Versioned action strings (R-09). ADR-010 `defusedxml` + SHA-256 snapshots (R-10). ADR-011 RapidFuzz threshold 88 (R-11, watchlist.py:47). ADR-012 Loopback API (R-12). ADR-013 Hard-coded config (R-14). ADR-014 Idempotent migrations re-run every start (R-15). ADR-015 Synthetic data only (R-13). ADR-016 Recommend-only (R-16).

## 10. Phase 4 Decisions Summary (proposed, user decides at sign-off)

D1 process model and ordering; D2 `aml_investigator` role and pinning trigger; D3 untrusted-input and output handling; D4 data minimization; D5 secrets; D6 provider/model versioning; D7 audit triggers; D8 retention and residual risk; D9 asynchronous, publish-nothing, recommend-only; D11 hallucination controls (FR-011, ADR-027: grounding checks, labels, evaluation set); D10 non-root container user for all services (`useradd --system --uid 10001 app`, `USER app`). Delta 2026-11-23, proposed ADRs (final ids: P-A, P-E, P-F, P-G -> ADR-028; P-C -> ADR-029; P-B, P-D -> ADR-030): (P-A) network segmentation: `internal`/`ingress`/`egress` networks and membership (section 1a); (P-B) anthropic egress enabled by override file `compose.anthropic.yaml`, no host-restricting proxy, RR-24 accepted; (P-C) self-hosted `llm` service (Ollama, baked weights, internal only, `LLM_MODE=local`, `LOCAL_LLM_URL`); (P-D) `DATA_CLASSIFICATION` startup gate ordering (validate before key read or network; audit stamps `inputs.data_classification`); (P-E) dedicated `watchlist-fetch` one-shot service (profile `fetch`) replaces in-`ingest` OFAC download; (P-F) `api` keeps ingress-network outbound route as accepted RR-23; (P-G) explicit Redpanda telemetry disable. D2 includes the `investigator_audit` view (no SELECT on `audit`). Implemented in Phase 4: D1-D7, D9-D11. Recorded residual / deferred: everything in section 8.
