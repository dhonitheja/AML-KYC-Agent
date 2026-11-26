---
id: "PLAN-002"
title: "Phase 4 investigation agent with hallucination controls and data residency (NFR-008)"
type: "implementation-plan"
status: "approved"
tier: "complex"
version: "1.0"
created: "2026-11-24"
author: "architect-planner-agent"
change_request: "Implement the Phase 4 investigation agent (FR-009/010/011) with grounding controls, revised for the NFR-008 delta: segmented networks and closed egress, self-hosted llm backend, DATA_CLASSIFICATION gate, isolated OFAC fetch"
addresses_fr: [FR-009, FR-010, FR-011]
addresses_nfr: [NFR-003, NFR-005, NFR-006, NFR-008]
addresses_us: [US-016, US-017, US-018, US-019, US-020, US-021, US-022, US-023, US-024, US-025, US-026, US-027, US-028, US-029]
constrained_by_adrs: [ADR-010, ADR-012, ADR-013, ADR-015, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026, ADR-027, ADR-028, ADR-029, ADR-030]
proposes_new_adrs: []
proposes_new_requirements: []
supersedes: "PLAN-001"
superseded_by: ""
---

# PLAN-002: Phase 4 investigation agent with hallucination controls and data residency (NFR-008)

## Summary
This plan supersedes PLAN-001. It builds the same Phase 4 `investigator` (FR-009/010/011, C1-C11 and T1-T5 carried forward), plus the NFR-008 delta signed off on 2026-11-24:
- three Compose networks (`internal` with `internal: true`, `ingress` for api only, `egress`);
- a self-hosted Ollama `llm` service and `LLM_MODE=local` (`LocalLLM`);
- the `DATA_CLASSIFICATION` startup gate, with anthropic egress only through the opt-in `compose.anthropic.yaml` override;
- the OFAC download moved into a one-shot `watchlist-fetch` service on `egress` only;
- explicit Redpanda telemetry disable;
- CI checks for NFR-008 AC-1..AC-8.

- **Tier:** complex (new trust boundaries and networks, a new service, new egress controls).
- **ADR impact:** no new ADRs. ADR-028, ADR-029 and ADR-030 (accepted 2026-11-24) and the amendments to ADR-013, ADR-015 and ADR-022 are applied. ADR-017..ADR-027 stay as in PLAN-001.
- **Security impact: YES.** Boundaries B8-B19 (ARCH-001 section 6.2). See Security Considerations.
- **Why a new plan rather than an in-place edit:** the delta adds a service, two compose files, networks, a new backend and a new gate. That is a structural rewrite of PLAN-001's C2/C5/C7/C8/C10/C11, so PLAN-001 is set `status: superseded`, `superseded_by: "PLAN-002"`.

## Existing work-in-progress (unreviewed drafts)
A stalled earlier run left these files in the working tree. They predate the NFR-008 delta and were never reviewed against PLAN-001 or this plan. **The code and test authors MUST treat them as unreviewed drafts and reconcile them against this plan, not as approved work.** Keep what matches; rewrite what does not. This plan does not modify them.

| File | State | Known divergence from this plan (not exhaustive) |
|---|---|---|
| `investigator.py` (untracked, 421 lines) | draft | `load_config` accepts only `stub|anthropic` (line 40-42). It has no `DATA_CLASSIFICATION` gate, no `local` mode and no `LOCAL_LLM_URL`. `DEFAULT_MODEL` is applied without the mode-aware rule. No `data_classification` on rows. `params()` (line 262) is not per backend. The log allow-list is unverified |
| `llm.py` (untracked, 130 lines) | draft | No `LocalLLM`, no `_NoRedirect`/`ProxyHandler({})` opener, no `params()` per backend |
| `grounding.py` (untracked) | draft | Must be checked against the CS-008 regexes and the 19 money cases |
| `sql/004-investigation.sql` (untracked) | draft | Must be checked against the CS-010 DDL order and idempotency |
| `tests/conftest.py` (untracked) | draft | Does not clear the `LLM_MODE`/`DATA_CLASSIFICATION`/`LOCAL_LLM_URL`/`LLM_MODEL` env vars (T1) |
| `tests/test_grounding.py`, `tests/test_llm.py` (untracked) | draft | `test_llm.py` has no `LocalLLM` cases |
| `compose.yaml` (modified) | draft | No networks. Investigator has `LLM_MODEL: ${LLM_MODEL:-claude-opus-5-5}` (forbidden by ADR-030) and mounts `anthropic_api_key` in the base file (must move to the override). No `llm`, no `watchlist-fetch`, no telemetry flag |
| `Dockerfile`, `.gitignore` (modified) | draft | Appear to match C4/C3; verify |
| `requirements.txt` (modified) | draft | `anthropic==1.17.0`. Re-run `pip index versions anthropic` and pin the exact latest 1.x; do not trust the draft value (ADR-022) |
| `secrets/demo/` (untracked) | draft | `investigator_db_password` (synthetic) and an empty `anthropic_api_key`; matches C3 |

## Requirements Addressed
Legend: **C** = source change (Source File Changes), **T** = test file (New Test Scenarios). "pure" tests need no infrastructure; "stack" tests run in the `ingest` container against postgres; "CI" means a workflow step in C10.

### FR-009 (carried from PLAN-001, unchanged)
| Req ID | Title | Relevant ACs -> Task / Test |
|---|---|---|
| FR-009.1 | Consumer | AC-1 C7/T5 pure (`consumer_config`); AC-2 C7/T5 stack (failure before txn-2 commit, re-handle gives one row) |
| FR-009.2 | Evidence gathering | AC-1 C7/T5 stack + C10 CI (AML-1042: 2 credits + debit ids); AC-2 C7/T5 pure (screening snapshot hash); AC-3 C7/T5 stack + T4 |
| FR-009.3 | Narrative output | AC-1 C7/T5 pure `build_drafted_row`; AC-2 C6/T2 (enum); AC-3 C7/T5 pure |
| FR-009.4 | Citation integrity | AC-1 C6, C7/T2 + T5 stack (stub cites fabricated id, no drafted row) |
| FR-009.5 | One draft per txn | AC-1 T5 stack (call-counting stub); AC-2 C1, C10 (CI runs `migrate` twice); AC-3 T5 stack (duplicate insert raises UniqueViolation); AC-4 T5 stack |
| FR-009.6 | Recommend-only | AC-1 T5 stack (scored/alerted rows byte-identical); AC-2 C1/T5 stack (`has_table_privilege`) |
| FR-009.7 | Skipped alerts | AC-1..AC-7 C7/T5 pure (`build_skipped_row`, reason enum, alert_key) + T5 stack (unknown, malformed, redelivered bad alert) |
| FR-009.8 | No onboarding data | AC-1 C7/T5 pure (evidence keys) + T5 stack (role cannot read `kyc_applications`) |
| FR-009.9 | Forged alerts (W2) | AC-1..AC-3 C7/T5 stack + T4 `forged_not_alerted` |
| FR-009.10 | Long evidence (W1) | AC-1..AC-3 C7/T5 pure + T4 `many_credit_ids` |

### FR-010 (revised to v1.2)
| Req ID | Title | Relevant ACs -> Task / Test |
|---|---|---|
| FR-010.1 | Mode selection | AC-1, AC-2, AC-3 (`local` accepted) C7/T5 pure `load_config` |
| FR-010.2 | Deterministic stub | AC-1 C5/T3; AC-2 T1 guard + C10 (no key, no route out in CI) |
| FR-010.3 | Config / real mode opt-in | AC-1, AC-4, AC-6, AC-7, AC-8 C7/T5 pure with `DATA_CLASSIFICATION=synthetic`; AC-2 T5 stack (`stub-v1`, `investigation-prompt-v2`); AC-3 T5 stack (key absent from audit rows and captured logs); AC-5 T5 pure; AC-9 T5 pure in stub AND local (key reader raises if called); AC-10, AC-11 T5 pure |
| FR-010.4 | Bounded calls | AC-1 T5 stack (forced-raise stub); AC-2 C5/T3 (timeout passed to client; LocalLLM timeout against a hanging loopback server); AC-3, AC-4, AC-5 C5/T3 |
| FR-010.5 | Local mode | AC-1, AC-2 C7/T5 pure; AC-3 C5/T3 (model id = configured `LLM_MODEL`, server echo ignored) + T5 stack (`handle` with `LocalLLM` against an in-process loopback fake server gives a drafted row with `model_version = LLM_MODEL`, same `prompt_version`); AC-4 T5 stack (`LocalLLM` to a refused loopback port gives `skipped(model_failure)` after `LLM_MAX_ATTEMPTS`, offset committed on the fake consumer); AC-5 C2 + T6 (`egress_check` from investigator, CI) + C10 opt-in `local-model` job; AC-6 C13 + C10 opt-in `local-model` job (completion served while `llm` is on `internal` only) |
| FR-010.6 | Synthetic-data gate | AC-1 T5 pure (key reader raises; `socket.socket` patched to raise); AC-2, AC-4, AC-6 T5 pure; AC-3 T5 pure (`load_config` passes; drafted and skipped rows carry `data_classification="synthetic"`) + T5 stack (rows stamped from config); AC-5 C8/T4 (`eval_investigator.main()` exits without synthetic) |

### FR-011
| Req ID | Title | Relevant ACs -> Task / Test |
|---|---|---|
| FR-011.1 | Claim-level output | AC-1..AC-3 C6/T2 |
| FR-011.2 | Grounding checks | AC-1..AC-4 C6/T2; AC-5, AC-7 C5, C7/T3 + T5 pure; AC-6 T2 (call-counting stub) |
| FR-011.3 | Consistency flag | AC-1..AC-3 C6/T2 |
| FR-011.4 | Labeling | AC-1, AC-2 C7/T5 pure + stack |
| FR-011.5 | Evaluation set | AC-1, AC-2, AC-5 C8/T4; AC-3 C8/T4 (refuses unless `LLM_MODE=anthropic` AND `DATA_CLASSIFICATION=synthetic`, through `load_model_config`); AC-4 C8/T4 (no psycopg import; AST check) |

### NFR-008 (new)
| Req ID | Title | Relevant ACs -> Task / Test |
|---|---|---|
| NFR-008 AC-1 | No route out (stub) | C2; C10 CI step: `egress_check` (T6) from `investigator` and `scorer`. The deny `api.anthropic.com:443` must fail; the allow `postgres:5432` must succeed (positive control, so the deny result is not vacuous) |
| NFR-008 AC-2 | No host ports except loopback api | C2; T7 `compose_check.py` over `docker compose --profile fetch --profile local config --format json` (CI) |
| NFR-008 AC-3 | Gate before key / network | C7/T5 pure (`load_config` and `main()` with the key reader, `socket.socket` and `psycopg.connect` patched to raise) |
| NFR-008 AC-4 | No evidence in logs | C7/T5 stack: `handle` for one drafted and one skipped scenario; captured output has no counterparty strings and no amounts (`$` form, integer cents, decimals); every line is JSON with keys only from the allow-list |
| NFR-008 AC-5 | No outbound calls in data modules | T8 `test_egress_static.py` (pure AST import scan of api/pipeline/scoring/kyc/rules; watchlist imports no DB/Kafka/Redis module and calls `urlopen` without `data`) + code review |
| NFR-008 AC-6 | Local mode: no route out, `llm` reachable | C10 opt-in `local-model` job: `egress_check --deny api.anthropic.com:443 --allow llm:11434` from investigator with `LLM_MODE=local`. The network half is also covered on every push by AC-1, because investigator network membership is identical in every mode of the base file (T7 asserts this) |
| NFR-008 AC-7 | Membership per ARCH-001 section 1a | T7 `compose_check.py` (CI), base file and the override variant |
| NFR-008 AC-8 | Fetch service isolated from DB | T7 (networks == {egress}) + C10 CI step `egress_check --deny postgres:5432` inside `watchlist-fetch` |
| NFR-008.4 | Agents do not forward data | C7 (no publish, no file, log allow-list) + AC-4 test |
| NFR-008.5 | Dev agents see synthetic data only | Process control: only `secrets/demo/` is used, and no real credentials are given to agents. Verified by review |

### Other NFRs touched
| Req ID | Relevant ACs -> Task / Test |
|---|---|
| NFR-003 | C1/T5 stack (role grants; no UPDATE/DELETE/TRUNCATE; the reverse guard) |
| NFR-005 | C6, C7 (advisory recommendation only; no `cases` write; no Kafka publish) |
| NFR-006 v1.2 | C3, C5, C7 (secrets, sanitized errors, allow-list); scope is repo/CI/demo, and NFR-008 governs deployments |

### User stories US-016..US-029
| US | AC -> Task / Test |
|---|---|
| US-016 | AC-1 T5 stack + C10 drafted-row check; AC-2 T5 stack (AML-1042 cites the 2 credit ids and the debit id); AC-3 T2 + T5 stack (fabricated id rejected); AC-4 T5 pure (no screenings gives no hit wording; no onboarding keys) |
| US-017 | AC-1 T5 stack (`model_version`, `prompt_version`, actor `investigator-v1`); AC-2 C1/T5 stack (UPDATE/DELETE raise; INSERT only) |
| US-018 | AC-1 T5 stack (redelivery gives no 2nd row); AC-2 T5 stack (duplicate insert raises UniqueViolation); AC-3 T5 stack (one drafted-or-skipped per alert) |
| US-019 | AC-1 T2 (enum); AC-2 T5 stack (scored/alerted rows unchanged; no `cases` privilege) |
| US-020 | AC-1, AC-2 T5 stack (malformed/unknown/not_alerted, origin key, redelivery); AC-3, AC-4 T3 + T5 stack (`model_failure`); AC-5 T3 + T5 pure (`grounding_failure`, `failed_checks`); AC-6 T5 pure + T4 `many_credit_ids` |
| US-021 | AC-1 T5 pure (model id per mode: stub `stub-v1`, local = `LLM_MODEL`, anthropic default `claude-opus-5-5`) + T5 stack (stub and local rows); AC-2 T5 pure (bogus mode, anthropic without synthetic, local without URL/model) |
| US-022 | AC-1 T3 (byte-identical stub) + C10 (no key in CI); AC-2 T5 stack (`stub-v1`) |
| US-023 | AC-1..AC-3 T2; AC-4 T3 + T5 pure |
| US-024 | AC-1..AC-3 T5 pure + stack; AC-4 C1/T5 stack |
| US-025 | AC-1..AC-4 T2 |
| US-026 | AC-1 T4 (8 scenarios, UUID-only synthetic ids); AC-2 T4 in CI; AC-3 C8 (opt-in report); AC-4 T1 + C10 (no key, no egress route) |
| US-027 | AC-1..AC-5 T5 stack + T4 `forged_not_alerted` |
| US-028 | AC-1 = NFR-008 AC-1 (C10/T6); AC-2 = NFR-008 AC-2 (T7); AC-3 = FR-010.6 AC-1/AC-2 (T5 pure); AC-4 = NFR-008 AC-4 (T5 stack); AC-5 = NFR-008 AC-7/AC-8 (T7 + C10/T6) |
| US-029 | AC-1 T5 stack (loopback fake server, `model_version = LLM_MODEL`, grounding applied) + C10 opt-in job (real Ollama); AC-2 T5 pure; AC-3 = NFR-008 AC-6 (C10 opt-in job; network half on every push via AC-1); AC-4 T5 stack (refused port gives `model_failure`, offset committed) |

## ADR Guardrails
| ADR | Decision | How this plan respects it |
|---|---|---|
| ADR-010 | defusedxml, size cap, SHA-256 snapshot | `watchlist.refresh()` code unchanged; only the service it runs in changes (C2 `watchlist-fetch`) |
| ADR-012 | Loopback API, no auth | `ports: ["127.0.0.1:8000:8000"]` unchanged; api joins `ingress` only to publish it |
| ADR-013 (+ amendment 2026-11-24) | Hard-coded config; `SDN_FILE` only env for Phase 1-3 | New env vars exist only on `investigator` (and `eval_investigator.py`); Phase 1-3 services unchanged |
| ADR-015 (+ amendment) | Synthetic data only (repo/CI/demo) | Demo secrets and fixtures stay synthetic; RR-1/2/3/6 re-assessment noted in README (C11) |
| ADR-017 | Single-process confluent consumer, commit after DB | C7: group `aml-investigator-v1`, auto-commit off, model call outside DB txns |
| ADR-018 | `aml_investigator` role, `investigator_audit` view, two-way guard | C1; C7 never uses `pipeline.DSN`, `RETURNING` or SELECT on `audit` |
| ADR-019 | Untrusted input/output | C7 `<evidence>` delimiting + escaping; C6 strict pydantic; LocalLLM output treated identically (B16) |
| ADR-020 | Allow-list, `SUBJECT_ACCOUNT` alias, payload hash | C7 `build_evidence`, `evidence_sha256`, `prompt_sha256`; same payload for local and anthropic |
| ADR-021 | Docker secret files, env fallback for dev | C2/C12: key secret mounted only by the override; read only after the gate |
| ADR-022 (+ 2026-11-23 and 2026-11-24 amendments) | Exact SDK pin, own retry, fixed params, no compose model default | C5, C9; compose `LLM_MODEL: ${LLM_MODEL:-}`; the `claude-opus-5-5` default only in the anthropic branch of `load_config` |
| ADR-023 | Combined partial unique index for draft/skip | C1 unchanged |
| ADR-024 | Immutability triggers | C1; tests never TRUNCATE/UPDATE/DELETE |
| ADR-025 | Retention, no deletion path | No delete code; RRs documented (C11) |
| ADR-026 | Non-root uid 10001 | C4 for Dockerfile-built services (including `watchlist-fetch`); `llm` non-root if the pinned image allows (C13), else RR-25 |
| ADR-027 | Grounding controls + eval set | C6, C8; applied to all three backends |
| ADR-028 | Three networks, closed egress, `watchlist-fetch`, explicit Redpanda telemetry disable | C2 membership exactly per ARCH-001 section 1a; T7 asserts it; C2 kafka telemetry flag; C10 OFAC command change |
| ADR-029 | Ollama `llm` service, digest-pinned, baked weights, stdlib `LocalLLM` | C13 (`llm.Dockerfile`), C2 (`llm` service), C5 (`LocalLLM`, no new dependency) |
| ADR-030 | `DATA_CLASSIFICATION` gate, stamp on every row, anthropic egress only via override | C7 gate order, C12 `compose.anthropic.yaml`, C8 eval reuses steps 1-3 |

## ADR Conflicts (if any)
None. Two implementation choices sit inside ADR latitude and are recorded so the reviewer can check them:
- **Weights baked at image build (ADR-029 allows "baked into the image or a local volume").** The build of `llm.Dockerfile` downloads the weights once. This is build-time egress with no customer data in the image, the same class as NFR-008.3(c). NFR-008.3(c) names only `pip install`, so Requirements Sync should widen its wording (see New Requirements). This is not a new egress path at runtime.
- **`llm` behind Compose profile `local`.** ADR-028 fixes network membership, not start-up defaults. A profile keeps the multi-GB build out of the default `up` and CI. Network membership is unchanged when the profile is active. `investigator` does NOT `depends_on: llm` (a dependency on a disabled profile service breaks the default `up`); an absent server yields `skipped(model_failure)` (FR-010.5 AC-4).

## Security Considerations
| Concern (boundary) | Control | Where it lands |
|---|---|---|
| Config/secrets to services (B8) | The key is read only when `LLM_MODE=anthropic` AND the gate passed. The key secret is mounted only by `compose.anthropic.yaml`, so the base file has no key mount. Errors name the variable, never its value. `LOCAL_LLM_URL` and the DSN are never logged. `.gitignore` keeps `secrets/*` ignored and `secrets/demo/` tracked | `investigator.load_model_config`, `compose.yaml`, `compose.anthropic.yaml`, `.gitignore` |
| Investigator DB password (B8a) | Unchanged from PLAN-001: one file, read by `migrate` and the investigator, no fallback. It is read in step 4 only, after the gate. RR-15 accepted | `compose.yaml` (migrate), `sql/004`, `investigator.load_config` |
| OFAC download (B9, B17) | Runs only in `watchlist-fetch`: profile `fetch`, `networks: [egress]`, not on `internal`, no secrets, no `environment`, only mount `./watchlists:/app/watchlists` (rw). api/scorer mount it `:ro`. `refresh()` unchanged (defusedxml, 128 MiB cap, Record_Count, atomic replace, SHA-256). AC-8 probe in CI. RR-18 accepted | `compose.yaml`, T6/T7, C10 |
| Forged / untrusted alert (B10) | Unchanged from PLAN-001 (pointer only; `alerted.v1` gate; origin-keyed skips) | `investigator.handle` |
| Investigator DB role (B11) | Unchanged (SELECT on `transactions` + view; INSERT on `audit`; two-way guard; immutability triggers) | `sql/004-investigation.sql` |
| Anthropic egress (B12) | Two independent controls: (1) the `DATA_CLASSIFICATION=synthetic` gate in `load_model_config`, before any key read, socket, DB or Kafka; (2) the network route exists only with `-f compose.anthropic.yaml`. Every row stamps `inputs.data_classification` from validated config. Egress is not host-restricted: RR-24 accepted. RR-20 applies only to synthetic deployments | `investigator.load_model_config`, `build_drafted_row`, `build_skipped_row`, `compose.anthropic.yaml` |
| Model output untrusted (B13), all three backends | Strict `Draft` (`extra=forbid`), citation subset, four grounding checks, retry then skip, no tools, summary never rendered. `format: "json"` in local mode is a syntax hint only; validation stays authoritative. RR-21 accepted | `grounding.py`, `investigator.validate_draft`, `llm.complete_with_retry` |
| Superuser/migrate (B14) | Unchanged (immutability triggers; initdb mounts only 001) | `compose.yaml`, `sql/004` |
| Supply chain (B15) | `anthropic` exact `==` pin from `pip index versions` (re-verified, not taken from the draft). Ollama base image pinned `@sha256:<digest>` (resolve with `docker buildx imagetools inspect ollama/ollama:<tag>`). The model tag is fixed by build arg, and its digest is recorded from `ollama list` at build in DI-011/README. No runtime pull. No new Python dependency for local mode (stdlib urllib). RR-22 accepted | `requirements.txt`, `llm.Dockerfile`, DI-011 note |
| Investigator to `llm` (B16) | Both ends on `internal` only. `LocalLLM` uses `build_opener(ProxyHandler({}), _NoRedirect)` (proxy env vars and 3xx cannot reroute evidence). It sends no auth header and holds no secret. Errors are sanitized to class[:status] and not chained. URL, body and response are never logged. `num_predict` 4096 caps output; `done_reason=length` is non-retryable. Ollama is not run with `OLLAMA_DEBUG` (verify the server logs carry no prompt body). RR-1 (plaintext hop) accepted | `llm.LocalLLM`, `compose.yaml` (`llm`), C10 opt-in job log check |
| api's technical outbound route (B18) | api on `internal` + `ingress` only. AST import scan (T8) proves api/pipeline/scoring/kyc/rules import no `urllib`/`requests`/`httpx`/`socket`/`http.client`/`aiohttp`/`anthropic`. Non-root; no secrets. RR-23 accepted | `compose.yaml`, T8 |
| Redpanda telemetry (B19) | Blocked by `internal`, and also disabled explicitly in config. The CI step asserts the effective cluster value is `false` | `compose.yaml` (`kafka` command), C10 |
| Data-holding services with no route out (NFR-008.1) | Every service declares `networks:` explicitly, so none falls back to `default`. `internal: true` on `internal`. T7 fails if any service is on `default` or an unexpected network | `compose.yaml`, T7 |
| Agents forwarding data (NFR-008.4) | No Kafka produce, no file write, no other service call from the investigator. JSON log lines use the key allow-list `{transaction_id, alert_key, outcome, attempts, latency_ms}` only, startup included | `investigator._log`, `main` |
| `llm` container user (RR-25) | Run as uid 10001 if the pinned image works with `OLLAMA_MODELS` and `HOME` set to paths that uid can read and write; otherwise accept RR-25 and say so in README | `llm.Dockerfile`, `compose.yaml` |
| Open security NFRs | NFR-003, NFR-005, NFR-006, NFR-008 (`focus_track: security`) are all addressed above; NFR-008 AC-1..AC-8 are mapped in Requirements Addressed | T5-T8, C10 |

## Source File Changes
Each item lists **C** number, file, CS reference and what changes relative to PLAN-001. "(carried)" means PLAN-001's text still holds verbatim; it is restated briefly so this plan stands alone.

### C1 - sql/004-investigation.sql (new) - carried
- **CS reference:** CS-010 (follow the DDL order exactly). **ACs:** FR-009.5 AC-2/AC-3, FR-009.6 AC-2, FR-009.8, FR-009.9.
- **What to change:** one BEGIN/COMMIT block:
  - `set_config('aml.investigator_password', :'investigator_password', true)`;
  - a DO block that runs CREATE ROLE if the role is absent, else ALTER ROLE PASSWORD;
  - `CREATE OR REPLACE VIEW investigator_audit` (five actions including `alerted.v1`);
  - grants: SELECT on transactions and the view, INSERT on audit, USAGE on `audit_event_id_seq`;
  - the two `CREATE UNIQUE INDEX IF NOT EXISTS` indexes;
  - `audit_investigator_guard` and `audit_immutable`, both with `SET search_path = pg_catalog, public` and not SECURITY DEFINER;
  - three triggers, each created only if absent (`pg_trigger` check).
- It must succeed when run twice. No NFR-008 change: there is no schema change, because `data_classification` lives in `inputs`.
- **Side effects:** the immutability triggers apply to all roles. Existing tests only INSERT and roll back.

### C2 - compose.yaml (revised)
- **CS reference:** CS-008 (Deployment, Component Interactions), CS-005/CS-006 deployment notes, CS-010, DI-011; ARCH-001 section 1a.
- **Lines to modify:** the whole file (currently about 89 lines). The service blocks for kafka (2-10), postgres (17-30), api (53-61) and investigator (71-81) change, and `llm`, `watchlist-fetch` and top-level `networks` are added.
- **What to change:**
  - **Top-level networks:**
    ```yaml
    networks:
      internal: {internal: true}
      ingress: {}
      egress: {}
    ```
  - **Every service gets an explicit `networks:` list** (none may land on `default`):
    - `kafka`, `topic`, `postgres`, `redis`, `migrate`, `scorer`, `ingest`, `investigator`, `llm`: `[internal]`;
    - `api`: `[internal, ingress]`;
    - `watchlist-fetch`: `[egress]`.
  - **Host ports:** only `api` keeps `ports: ["127.0.0.1:8000:8000"]` (unchanged). Confirm `postgres`, `redis` and `kafka` have no `ports` and no `expose`-to-host; there are none today (NFR-008.2).
  - **kafka telemetry (B19):** add the explicit disable of Redpanda usage reporting.
    - Verify against the pinned `v24.3.10` image first. The candidate cluster property is `enable_metrics_reporter`; ARCH-001's `redpanda.enable_usage_stats` wording is a guess to check. Confirm with `docker compose exec kafka rpk cluster config get enable_metrics_reporter`.
    - Preferred: a start-time setting in the `kafka` command (e.g. `--set redpanda.enable_metrics_reporter=false`, if the v24.3.10 bootstrap honours it).
    - Fallback if no start-time flag takes effect: append `rpk cluster config set enable_metrics_reporter false -X brokers=kafka:9092` to the idempotent `topic` command. Record which one was used in the commit and in README.
  - **postgres:** keep `./sql/001-foundations.sql:/docker-entrypoint-initdb.d/001-foundations.sql:ro` only (carried).
  - **migrate:** carried from PLAN-001: the secret `investigator_db_password` and the shell-form single psql session running `\set investigator_password ...`, then `\i` 002, 003, 004 with `ON_ERROR_STOP=1`. Add `networks: [internal]`.
  - **investigator:**
    ```yaml
    investigator:
      build: .
      entrypoint: ["python","-u","investigator.py"]
      networks: [internal]
      environment:
        LLM_MODE: ${LLM_MODE:-stub}
        DATA_CLASSIFICATION: ${DATA_CLASSIFICATION:-}
        LOCAL_LLM_URL: ${LOCAL_LLM_URL:-}
        LLM_MODEL: ${LLM_MODEL:-}
        LLM_TIMEOUT_SECONDS: ${LLM_TIMEOUT_SECONDS:-30}
        LLM_MAX_ATTEMPTS: ${LLM_MAX_ATTEMPTS:-3}
      secrets: [investigator_db_password]
      depends_on:
        topic: {condition: service_completed_successfully}
        migrate: {condition: service_completed_successfully}
      restart: on-failure
    ```
    - There is no `claude-opus-5-5` default (ADR-030) and no `DATA_CLASSIFICATION` or `LOCAL_LLM_URL` default; empty means unset in code.
    - There is no `anthropic_api_key` in the base file; it moves to C12.
    - There is no `depends_on: llm` (see ADR Conflicts).
  - **llm (new):**
    ```yaml
    llm:
      build: {context: ., dockerfile: llm.Dockerfile, args: {OLLAMA_MODEL: "${OLLAMA_MODEL:-<default model tag, see Open Question 1>}"}}
      profiles: ["local"]
      networks: [internal]
      restart: on-failure
    ```
    - No `ports`, no `secrets`, no `volumes` (the weights are in the image), no `OLLAMA_DEBUG`.
    - Add `user: "10001"` only if C13 confirms it works; otherwise leave it out and record RR-25.
  - **watchlist-fetch (new):**
    ```yaml
    watchlist-fetch:
      build: .
      profiles: ["fetch"]
      entrypoint: ["python","-u","watchlist.py"]
      networks: [egress]
      volumes: ["./watchlists:/app/watchlists"]
      restart: "no"
    ```
    - No `secrets`, no `environment`, no `depends_on`.
  - **Top-level `secrets`:** keep only `investigator_db_password` in the base file. `anthropic_api_key` moves to C12.
- **Side effects:**
  - The network names change the container DNS reachability matrix. Every existing hostname (`postgres`, `kafka`, `redis`, `api`) stays reachable from the `ingest` test container, because everything is on `internal`.
  - CI `curl localhost:8000` still works via `ingress`.
  - Existing users who relied on `docker compose run ... ingest watchlist.py` for the OFAC download now get a DNS failure. The README and CLAUDE.md change in C11.

### C3 - secrets/demo/ and .gitignore - carried
- `secrets/demo/investigator_db_password` (synthetic value, trailing newline) and `secrets/demo/anthropic_api_key` (empty) as in PLAN-001. The empty key file is now referenced only by C12's default.
- `.gitignore`: `secrets/*`, `!secrets/demo/`, `.jetro/`, `.claude-flow/` (the draft already has these; verify).
- **ACs:** FR-010.3 AC-3/AC-10, NFR-006.

### C4 - Dockerfile - carried
- `ENV PYTHONDONTWRITEBYTECODE=1`; `RUN useradd --system --uid 10001 app && mkdir -p /app/state && chown app /app/state`; `USER app` before `ENTRYPOINT` (the draft has these; verify).
- `COPY tests ./tests` is already present, so `tests/egress_check.py` (T6) is available in every app-image container: investigator, scorer and watchlist-fetch.
- **Side effects:** `watchlist-fetch` runs as uid 10001 and writes `./watchlists/sdn.xml` through a host bind mount. On Docker Desktop (Windows/macOS) this works; on Linux the host directory must be writable by uid 10001 (README note, C11).

### C5 - llm.py (revised)
- **CS reference:** CS-009 v1.2, DI-010, DI-011. **ACs:** FR-010.2, FR-010.4, FR-010.5 AC-3/AC-4, FR-011.2 AC-5/AC-7, NFR-008 (B16).
- **Carried (PLAN-001 C5, unchanged):**
  - `PROMPT_VERSION = "investigation-prompt-v2"`;
  - `StubLLM` (templates and test-hook `script`/`calls`);
  - `AnthropicLLM`, with the verified SDK facts: `anthropic.Anthropic(api_key=..., max_retries=0, timeout=...)`, `messages.create(model, max_tokens=16000, output_config={"effort": "low"}, system, messages)`, no temperature/top_p/top_k/thinking/tools/stream/fallbacks, `stop_reason` refusal/max_tokens non-retryable, text blocks only, `response.model`, lazy import, `APITimeoutError` checked before `APIConnectionError`;
  - `Failure`, `complete_with_retry` with backoff `min(30, 2**(n-1)) * (0.5 + rng())`, and `_sanitize`.
- **New: `LocalLLM(url, model, timeout)`:**
  - Module-level `_NoRedirect(urllib.request.HTTPRedirectHandler)` whose `redirect_request` returns `None`.
  - The opener is built once in `__init__`: `urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)`. Never `urlopen`.
  - `complete(system, user)`: one `POST {url.rstrip('/')}/api/chat`, header `Content-Type: application/json` only, body `{"model": model, "stream": false, "format": "json", "messages": [{"role":"system","content":system},{"role":"user","content":user}], "options": {"temperature": 0, "num_predict": 4096}}`, `opener.open(req, timeout=timeout)`.
  - Returns `(body["message"]["content"], self.model)`; the server's model echo is ignored.
  - **Error mapping** (sanitized `"<Class>[:<status>]"`, never chained):
    - `HTTPError` 429/5xx: retryable. Other 4xx and 3xx: non-retryable `model_failure`.
    - `URLError`, `TimeoutError`/`socket.timeout`, `ConnectionError`, `http.client.RemoteDisconnected`: retryable.
    - A 200 with an `error` key, a non-JSON body, or missing/empty/non-string `message.content`: retryable validation failure (`error="validation"`, `last_reason=model_failure`).
    - `done_reason == "length"`: non-retryable `model_failure`.
  - The way `complete_with_retry` classifies "retryable vs not" must be backend-neutral. For example, backends raise one small internal exception type carrying `(tag, retryable)`, and `complete_with_retry` reads that. Reconcile this with the draft `_retryable` (line 101), which is anthropic-specific.
- **New: `params()`** on each backend: stub `{}`; anthropic `{"max_tokens": 16000, "effort": "low"}`; local `{"temperature": 0, "format": "json", "num_predict": 4096}`. The values come from the same constants the request uses, so they cannot drift.
- **Functions/classes affected:** `LocalLLM`, `_NoRedirect`, `params()` (all three backends), `complete_with_retry` retry classification, `_sanitize`.
- **Side effects:** imported by `investigator.py`, `eval_investigator.py` and tests. `llm.py` is a permitted network module (ADR-029); it is excluded from the T8 scan list by design.

### C6 - grounding.py (new, pure) - carried
- **CS reference:** CS-008 "grounding.py". Unchanged from PLAN-001 C6:
  - `Finding`/`Draft` with `extra="forbid"` and the summary-citation validator;
  - `check_grounding` with the checks `amounts`, `counterparties`, `rules`, `sanctions`;
  - `consistency`;
  - the exact money regex `\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|[.,]\d)`, integer cents, exactly 2 fractional digits, and the malformed guard (`\$\s?\d` count == match count);
  - the rule regex `\b[a-z]+(?:_[a-z]+)+\b`, excluding the recommendation values;
  - the sanctions term list;
  - `from watchlist import normalize`.

### C7 - investigator.py (revised)
- **CS reference:** CS-008 v1.2, data-flow section 2a. **ACs:** all of FR-009, FR-010.1/10.3/10.4 AC-1/10.5/10.6, FR-011.4, NFR-008 AC-3/AC-4, NFR-008.4.
- **Carried (PLAN-001 C7):**
  - `consumer_config`, `build_evidence`, `render_prompt`, `validate_draft`, `build_drafted_row`, `build_skipped_row` (five-reason set), `AlertIn`, the pure `decide(...)` gate helper, and `handle(msg, db, llm, cfg)` steps 0-6;
  - startup assertions: `current_user = 'aml_investigator'`, and `alerts` has 1 partition;
  - `consumer.commit(asynchronous=False)` after each `handle`;
  - no `pipeline.DSN`; `SET LOCAL lock_timeout='5s'`, `statement_timeout='10s'`.
- **Config split** (draft lines 37-65 replaced):
  - `load_model_config(env, read_key) -> ModelConfig`: CS-008 steps 1-3, pure. `read_key` is an injected callable so tests can make it raise.
    1. Normalize: `get = lambda k: (env.get(k) or "").strip() or None` (empty means unset for `LLM_MODE`, `DATA_CLASSIFICATION`, `LOCAL_LLM_URL`, `LLM_MODEL`).
    2. `mode = get("LLM_MODE") or "stub"`, which must be in {stub, local, anthropic}. `classification = get("DATA_CLASSIFICATION") or "customer"`, which must be in {customer, synthetic}. Either failure exits in every mode.
    3. **Gate:** if `mode == "anthropic"` and `classification != "synthetic"`, exit with a clear message naming the variable. This happens before any key read.
    4. Mode-specific:
       - anthropic: the key comes from `read_key(env.get("ANTHROPIC_API_KEY_FILE", "/run/secrets/anthropic_api_key"))`. If the file is absent, fall back to `ANTHROPIC_API_KEY`. If neither yields a key, exit. `model = get("LLM_MODEL") or "claude-opus-5-5"`.
       - local: `LOCAL_LLM_URL` is required, else exit (FR-010.5 AC-1). `LLM_MODEL` is required, else exit (AC-2). No key is read.
       - stub: read nothing; `model = "stub-v1"`.
  - `load_config(env, read_key, read_file) -> Config`: calls `load_model_config` first, then step 4:
    - the DB password file (missing/empty exits; no fallback);
    - `INVESTIGATOR_DB_HOST` default `postgres`;
    - `LLM_TIMEOUT_SECONDS` > 0, default 30;
    - `LLM_MAX_ATTEMPTS` 1..10, default 3.
  - Neither function opens a socket, DB or Kafka connection, or imports `anthropic`.
- **Exit messages:** `SystemExit("<VAR>: <reason>")`. Never include the key, the password, the URL or the DSN.
- **`make_llm(cfg)`:** builds `StubLLM()`, `LocalLLM(cfg.local_url, cfg.model, cfg.timeout)` or `AnthropicLLM(key, model, timeout)`. `params(cfg, llm)` = `{llm_mode, model, request: llm.params(), timeout_s, max_attempts}` (replaces the draft's `params(cfg)` at line 262).
- **`data_classification`:** `build_drafted_row` and `build_skipped_row` take it from `cfg` (validated config only). Every row in every mode carries `inputs.data_classification`.
- **Logging** (`_log`, draft line 335):
  - Each line is one JSON object with keys only from `{transaction_id, alert_key, outcome, attempts, latency_ms}`. Startup and shutdown use `{"outcome": "started"}` / `{"outcome": "stopped"}` only.
  - Exceptions are logged as `{"outcome": "error:<ClassName>"}` with no message.
  - Nothing else is printed: no evidence, prompt, response, URL, DSN, key or SDK/driver message.
- **`main()` order:**
  1. `cfg = load_config(os.environ, ...)`. On exit, no import of `anthropic`, psycopg connect or Kafka consumer has happened.
  2. Build the LLM.
  3. Connect to the DB and assert `current_user`.
  4. Create the consumer and assert 1 partition.
  5. Poll loop.
- **Lines to modify:** draft lines 19-75 (config), 262-315 (params/rows), 335-340 (log) and 389-421 (main). Reconcile everything else against CS-008.
- **Side effects:** `eval_investigator.py` imports `load_model_config`, `decide`, `build_evidence`, `render_prompt` and `validate_draft`. Tests import the pure functions.

### C8 - eval_investigator.py (new) and tests/eval/scenarios.json (new) - revised
- **CS reference:** CS-008 "Evaluation set" v1.2. **ACs:** FR-011.5 AC-1..AC-5, FR-010.6 AC-5.
- **scenarios.json:** carried. `"version": 1`, all ids are UUIDs, drafted scenarios set `db.alerted: true`. The 8 named scenarios: `AML-1042`, `clean`, `screening_hit`, `large_cash`, `injection_in_counterparty`, `malformed`, `many_credit_ids` (60+ ids), `forged_not_alerted`.
- **eval_investigator.py:**
  - `main(argv=None, env=os.environ)` calls `investigator.load_model_config(env, read_key)` (steps 1-3 only, never step 4). It then additionally requires `mode == "anthropic"`. Because the gate is inside `load_model_config`, anthropic without synthetic already exits before any key read.
  - It runs each scenario through `decide`, `build_evidence`, `render_prompt`, `complete_with_retry(AnthropicLLM(...), ...)` and validate + `check_grounding`. It writes `./eval-report.json` (path argument allowed) and prints the three rates.
  - No `psycopg` import; no DB connection.
- **How to run:** from a dev host with Python, or with `LLM_MODE=anthropic DATA_CLASSIFICATION=synthetic docker compose -f compose.yaml -f compose.anthropic.yaml run --rm -v "$PWD/eval:/out" --entrypoint python investigator eval_investigator.py /out/eval-report.json` after `mkdir -p eval` as yourself, adding `-u "$(id -u)"` on Linux (the override does not select the mode; the container user cannot write to `/app`, and a Docker-created `eval` would be root-owned). The base file has no route out, so it would fail there by design.

### C9 - requirements.txt - revised
- Add `anthropic==<exact latest 1.x from pip index versions anthropic>`. Re-verify; do not keep the draft `1.17.0` without checking.
- No other change: local mode adds no Python dependency.

### C10 - .github/workflows/ci.yml - revised
- **Job `benchmark`** (push, `timeout-minutes: 15`). Order of steps:
  1. **Static compose checks (before `up`, a few seconds; NFR-008 AC-2/AC-7/AC-8):**
     - `docker compose --profile fetch --profile local config --format json | python3 tests/compose_check.py base`
     - `docker compose -f compose.yaml -f compose.anthropic.yaml --profile fetch --profile local config --format json | python3 tests/compose_check.py anthropic`
     - `config` does not build images, so the `llm` image is never built on push.
  2. `docker compose up --build -d` (the `llm` and `watchlist-fetch` profiles stay inactive).
  3. **Readiness (carried):** `curl --retry 30 --retry-connrefused --retry-delay 2 --fail http://localhost:8000/alerts >/dev/null`, plus a check that `docker compose ps investigator` shows it running.
  4. `docker compose run --rm --entrypoint python ingest -m pytest -v` (includes T5 stack, T8, and the local-mode loopback tests).
  5. **Migrate twice (carried):** `docker compose run --rm migrate`.
  6. **Egress probes (NFR-008 AC-1, AC-8):**
     - `docker compose exec -T investigator python tests/egress_check.py --deny api.anthropic.com:443 --allow postgres:5432`
     - `docker compose exec -T scorer python tests/egress_check.py --deny api.anthropic.com:443 --allow postgres:5432`
     - `docker compose --profile fetch run --rm --no-deps --entrypoint python watchlist-fetch tests/egress_check.py --deny postgres:5432` (it does not download the OFAC list)
  7. **Telemetry (B19):** `docker compose exec -T kafka rpk cluster config get enable_metrics_reporter | grep -qx false` (use the property name verified in C2).
  8. `seed`, then `latency.py`, then the `/alerts` AML-1042 check (carried).
  9. **Drafted-row check (carried):** poll up to 60 s for `investigation.drafted.v1` with `case_id='AML-1042'`, `model_version='stub-v1'` AND `inputs->>'data_classification'='customer'`.
  10. The benchmark (carried).
  11. On failure: `docker compose logs`.
- **Budget:** the new steps add about 20 s (config), about 10 s (probes with a 3 s connect timeout each), plus a brief exec. That stays well within 15 min.
- **Job `local-model`** (new, `on: workflow_dispatch` only, `timeout-minutes: 30`, never on push):
  - This job is opt-in because the Ollama image plus baked weights (several GB) and CPU inference do not fit the 15-min push budget. It is the only automated evidence for NFR-008 AC-6, FR-010.5 AC-6 and the real-server half of US-029 AC-1/AC-3. The CI-runnable halves are covered on every push (AC-1 probe, loopback fake-server stack tests).
  - Steps:
    1. `docker compose --profile local build llm` (the build-time weights download, NFR-008.3(c)).
    2. `LLM_MODE=local LLM_MODEL=<same tag> LOCAL_LLM_URL=http://llm:11434 docker compose --profile local up -d`.
    3. `docker compose exec -T investigator python tests/egress_check.py --deny api.anthropic.com:443 --allow llm:11434` (AC-6).
    4. `docker compose exec -T investigator python -c "<LocalLLM(url, model, 120).complete one tiny JSON prompt; exit 0 on a non-empty string>"` (FR-010.5 AC-6: completion served while `llm` is internal-only).
    5. `seed`; poll up to 10 min for a drafted or skipped `investigation.*.v1` row for AML-1042 with `model_version = LLM_MODEL`.
    6. `docker compose logs llm` must not contain the AML-1042 counterparty strings (no prompt logging, DI-011).

### C11 - README.md and CLAUDE.md - revised
- **README** "Phase 4: investigation agent" section, covering:
  - stub/local/anthropic modes;
  - env vars `LLM_MODE`, `DATA_CLASSIFICATION`, `LOCAL_LLM_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ATTEMPTS`, plus `INVESTIGATOR_DB_PASSWORD_SECRET`, `ANTHROPIC_API_KEY_SECRET` and `OLLAMA_MODEL`;
  - networks (`internal`/`ingress`/`egress`, and that only api is published);
  - local mode: `docker compose --profile local build llm` (one-time, downloads weights at build), then `$env:LLM_MODE="local"; $env:LLM_MODEL="<tag>"; $env:LOCAL_LLM_URL="http://llm:11434"; docker compose --profile local up -d`;
  - anthropic mode: synthetic only, `$env:DATA_CLASSIFICATION="synthetic"; $env:LLM_MODE="anthropic"; docker compose -f compose.yaml -f compose.anthropic.yaml up -d`, with the key file via `ANTHROPIC_API_KEY_SECRET`;
  - the eval script;
  - recommend-only posture;
  - residual risks RR-15, RR-19, RR-20, RR-21, RR-23, RR-24, RR-25 (plus the ADR-015 amendment note that RR-1/2/3/6 must be re-assessed before real data);
  - the existing-volume note;
  - the Linux uid-10001 write permission for `./watchlists`.
- **README OFAC command** (line 48) is replaced by `docker compose --profile fetch run --rm watchlist-fetch`. The following `$env:SDN_FILE` + `--force-recreate api scorer` lines stay.
- **CLAUDE.md** (orchestrator to confirm the edit with the user; CLAUDE.md is a project-instructions file):
  - Phases 1-4.
  - The Real OFAC command becomes `docker compose --profile fetch run --rm watchlist-fetch`.
  - Config: replace "The only env var is `SDN_FILE`" with the investigator env list (ADR-013 amendment).
  - Networks and `compose.anthropic.yaml`.
  - The `llm` service and profile `local`.
  - Architecture entries for `investigator.py`, `llm.py`, `grounding.py`, `eval_investigator.py`.
  - initdb mounts only 001; `migrate` runs 002-004.
  - Non-root user.
  - Test split: `test_grounding`, `test_llm`, `test_eval_scenarios`, `test_egress_static` are pure; `test_investigator` is mixed; `tests/egress_check.py` and `tests/compose_check.py` are CI tools, not pytest.
  - The new CI steps and the opt-in `local-model` job.

### C12 - compose.anthropic.yaml (new)
- **CS reference:** CS-008 Component Interactions, ADR-030, ARCH-001 section 1a.
- **What to change:** an override file containing only:
  ```yaml
  services:
    investigator:
      networks: [internal, egress]
      secrets: [investigator_db_password, anthropic_api_key]
  secrets:
    anthropic_api_key: {file: "${ANTHROPIC_API_KEY_SECRET:-./secrets/demo/anthropic_api_key}"}
  ```
- **Verify:** check the merge with `docker compose -f compose.yaml -f compose.anthropic.yaml config`. The investigator must end up with both networks and both secrets, and no other service may change. T7 `anthropic` mode asserts this.
- **Side effects:** none on the base deployment. If the override is used with `LLM_MODE` unset, the investigator runs the stub with a route out; this is harmless (no outbound code path) and documented.

### C13 - llm.Dockerfile (new)
- **CS reference:** DI-011, ADR-029.
- **What to change:**
  - `FROM ollama/ollama:<tag>@sha256:<digest>`. The code author resolves the digest with `docker buildx imagetools inspect` and records it.
  - `ARG OLLAMA_MODEL`.
  - `ENV OLLAMA_MODELS=/models OLLAMA_NOPRUNE=1 OLLAMA_HOST=0.0.0.0:11434`.
  - `RUN ollama serve & pid=$!; for i in $(seq 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done; ollama pull "$OLLAMA_MODEL" && ollama list; status=$?; kill $pid; exit $status` (the pull status is kept, so a failed download fails the build, as in llm.Dockerfile). This is a build-time download only; the `ollama list` output (model ID digest) is recorded in DI-011 and the README.
  - `RUN chmod -R a+rX /models`.
  - Non-root (RR-25): try `RUN useradd --system --uid 10001 app` (or the image's equivalent) and `USER app` with `ENV HOME=/tmp`.
  - Verify the server starts and serves `/api/chat` as uid 10001 with `/models` read-only to it. If it does not, remove `USER` and leave RR-25 as accepted.
  - Keep the image `ENTRYPOINT`/`CMD` (`ollama serve`). There is no runtime `ollama pull` anywhere.
- **Side effects:** none on the app image. Built only with `--profile local` (or an explicit `build llm`).

## New Test Scenarios
The test author writes these from the FR/NFR/CS/DI specs, in parallel with the code (see Ordering). The draft tests listed under Existing work-in-progress must be reconciled, not trusted.

### T1 - tests/conftest.py (pure) - revised
- **FR:** FR-010.2 AC-2, NFR-008 AC-3 (support).
- **Test description:**
  - An autouse fixture that `delenv`s `ANTHROPIC_API_KEY`, `LLM_MODE`, `DATA_CLASSIFICATION`, `LOCAL_LLM_URL` and `LLM_MODEL`.
  - It monkeypatches `anthropic.Anthropic` (if importable) with a class whose constructor raises.
  - `LocalLLM` tests may only target `127.0.0.1` loopback servers started in-process.
- **Fixtures:** none new.

### T2 - tests/test_grounding.py (pure) - carried
- **FR:** FR-011.1..FR-011.3, FR-009.3 AC-2, FR-009.4. **US:** US-019 AC-1, US-023 AC-1..AC-3, US-025 AC-1..AC-4.
- **Money cases:** the parametrized table of all 19 CS-008 money cases. Also "$100000" against evidence of $100.00 fails, and "$81,000" against $80,900.00 fails.
- **Other checks:** counterparty, rule and sanctions positive/negative cases; `escalate_for_review` in text does not trip `rules`.
- **Schema rejections:** 0 or 11 findings; a statement over 300 chars; empty citations; a non-fired `rule`; a summary id that is in no finding; an extra field; a bad recommendation.
- **Consistency:** warning cases (no-action with a 60-point rule, or with a hit); the recommendation is never changed.
- **No model call:** `check_grounding` makes no model call.

### T3 - tests/test_llm.py (pure) - revised
- **FR:** FR-010.2, FR-010.4, FR-010.5 AC-3/AC-4, FR-011.2 AC-5/AC-7; DI-011.
- **Carried:**
  - stub determinism, and stub output passes `check_grounding` for each drafted scenario;
  - the retry loop with injected `sleep`/`rng`, including the last-reason ordering `[ungrounded, raise]` gives `model_failure` and `[raise, ungrounded]` gives `grounding_failure`;
  - the Anthropic fake: exact kwargs, constructor `max_retries=0` + `timeout`, text blocks only, `response.model`;
  - error classes via `cls.__new__`: 429/500/timeout/connection retried; 400/401/404 and refusal/max_tokens stop after 1 attempt;
  - the sanitized error contains no planted `sk-...` string.
- **New LocalLLM cases** (against a `http.server.ThreadingHTTPServer` on `127.0.0.1:0` in a daemon thread):
  - the request is `POST /api/chat`, and the body equals the DI-011 JSON exactly (`stream` false, `format` json, `options` temperature 0 and num_predict 4096), with no `Authorization` header;
  - a good body returns `(content, configured_model)` even when the server echoes a different `model`;
  - 500 and 429 are retried; 400, 404 and 422 stop after 1 attempt;
  - a 302 to another port is NOT followed (the redirect target server records no hit) and is non-retryable;
  - a refused port (bind then close a socket to get a free port) is retryable and exhausts to a `model_failure` `Failure` with attempts == max;
  - a hanging handler (sleeps longer than the timeout) is aborted at the timeout, which counts as a retryable attempt;
  - a 200 with `{"error": ...}`, a non-JSON body, or empty/non-string `message.content` each count as a retryable `validation` failure;
  - `done_reason: "length"` is non-retryable `model_failure`;
  - `HTTP_PROXY=http://127.0.0.1:<unused>` set in env does not affect the call (`ProxyHandler({})`);
  - the sanitized error string contains neither the URL nor the response text.
- **`params()`:** stub `{}`, anthropic `{max_tokens:16000, effort:"low"}`, local `{temperature:0, format:"json", num_predict:4096}`.
- **Fixtures needed:** a small loopback fake-server helper (in this file, or shared in `conftest.py` if T5 reuses it) that serves scripted responses and records requests.

### T4 - tests/test_eval_scenarios.py (pure) - revised
- **FR:** FR-011.5, FR-009.9, FR-009.10, FR-010.6 AC-5. **US:** US-026.
- **Carried:**
  - the file loads, has an int `version` and 8 or more scenarios covering the 8 names, and every id is a UUID;
  - each scenario goes through `decide`, `build_evidence`, `StubLLM`, `validate_draft` and `check_grounding`, and the actual outcome equals `expected`;
  - `many_credit_ids` assertions; `injection_in_counterparty` escaping;
  - `psycopg` is not imported by `eval_investigator.py` (AST).
- **New:** `eval_investigator.main(env=...)` exits non-zero for each of:
  - `LLM_MODE` unset;
  - `LLM_MODE=stub`;
  - `LLM_MODE=local` (+ URL/model);
  - `LLM_MODE=anthropic` with `DATA_CLASSIFICATION` unset;
  - `LLM_MODE=anthropic` with `DATA_CLASSIFICATION=customer`.

  In every one of these cases the injected key reader raises if called and `socket.socket` is patched to raise, proving it exits before any key read or network.

### T5 - tests/test_investigator.py (pure + stack) - revised
- **FR:** FR-009.1..FR-009.10, FR-010.1, FR-010.3, FR-010.4 AC-1, FR-010.5, FR-010.6, FR-011.4, NFR-008 AC-3/AC-4. **US:** US-016..US-021, US-024, US-027, US-028 AC-3/AC-4, US-029 AC-1/AC-2/AC-4.
- **Pure - `load_model_config` / `load_config` matrix** (tmp files, env dicts, `read_key` that raises unless the case expects a read; `socket.socket` and `psycopg.connect` patched to raise for the whole matrix):

  | Env | Expected |
  |---|---|
  | unset | stub, `customer`, `model_version` `stub-v1`, key never read (FR-010.1 AC-1, FR-010.6 AC-6) |
  | `LLM_MODE=bogus` | exits (FR-010.1 AC-2) |
  | `LLM_MODE=local` + URL + model | accepted, key never read (FR-010.1 AC-3, FR-010.3 AC-9) |
  | local, URL unset or `""` | exits (FR-010.5 AC-1) |
  | local, `LLM_MODEL` unset or `""` | exits (FR-010.5 AC-2) |
  | anthropic, `DATA_CLASSIFICATION` unset | exits, `read_key` never called (FR-010.6 AC-1, NFR-008 AC-3) |
  | anthropic, `DATA_CLASSIFICATION=customer` | exits (FR-010.6 AC-2) |
  | `DATA_CLASSIFICATION=bogus` in stub, local and anthropic | exits (FR-010.6 AC-4) |
  | anthropic + synthetic + key file | starts (FR-010.6 AC-3) |
  | anthropic + synthetic, no key | exits (FR-010.3 AC-1, AC-8) |
  | anthropic + synthetic, file + env both set | file wins (FR-010.3 AC-6) |
  | anthropic + synthetic, file absent + env set | env used (FR-010.3 AC-7) |
  | anthropic + synthetic, `LLM_MODEL` unset or `""` | model `claude-opus-5-5` (FR-010.3 AC-4) |
  | stub + `LLM_MODEL=x` | still `stub-v1` (FR-010.3 AC-5) |
  | empty or missing DB password file | exits (FR-010.3 AC-10) |
  | host unset | `postgres` (FR-010.3 AC-11) |
  | gate failure | the DB password reader is never called (gate before step 4) |
  | timeout/attempts out of range | exits |
  | any exit | the message contains no key, URL or password values |

- **Pure - `main()`:**
  - With anthropic and no classification, `main()` raises SystemExit, and the patched `psycopg.connect`, `confluent_kafka.Consumer` and `socket.socket` were never called. `anthropic` is not imported (check `"anthropic" not in sys.modules` after removing it first, or patch the import) (NFR-008 AC-3).
- **Pure - carried:**
  - `consumer_config`;
  - the `build_evidence` cases;
  - `build_drafted_row` labels;
  - `build_skipped_row` reason/key/NULL rules.
- **Pure - new:**
  - `build_drafted_row` and `build_skipped_row` carry `inputs.data_classification` equal to cfg (`customer` and `synthetic` variants);
  - `params.request` equals `llm.params()` for each backend;
  - `model_version` per mode (US-021 AC-1).
- **Stack (needs postgres)** - carried: the admin connection plus `SET ROLE aml_investigator`, fixture rows via `record_transaction` with a fresh `uuid4()`, fake `msg` with a large unique offset, plus all PLAN-001 cases:
  - one drafted row with `stub-v1`/`investigation-prompt-v2`;
  - redelivery dedupe;
  - failure before the txn-2 commit;
  - a `model_failure` skip redelivered;
  - unknown/malformed;
  - forged then genuine;
  - payload differs from `scored.v1`;
  - forced raise;
  - scored/alerted byte-identical;
  - key absent from audit/captured output;
  - guard and privilege checks;
  - no TRUNCATE.
- **Stack - new:**
  - drafted and skipped rows carry `inputs.data_classification = "customer"` under the default cfg, and `"synthetic"` when cfg says so (FR-010.6 AC-3 row half);
  - **local mode, drafted:** `handle` with `LocalLLM(url=<loopback fake server returning StubLLM's JSON for the same user prompt>, model="local-test-model")` gives a drafted row with `model_version='local-test-model'`, `prompt_version='investigation-prompt-v2'`, `params.request.num_predict=4096` and grounding passed (FR-010.5 AC-3, US-029 AC-1);
  - **local mode, unreachable:** `LocalLLM` to a refused loopback port with `max_attempts=2` and `sleep` patched gives exactly one `skipped(model_failure)` row with `attempts=2`, and the fake consumer recorded a commit (FR-010.5 AC-4, US-029 AC-4);
  - **AC-4 log assertion** (NFR-008 AC-4, US-028 AC-4): run `handle` for one drafted and one `not_alerted` skipped scenario with `capsys` and `caplog`. The captured text contains none of the fixture counterparty strings and none of the amounts, in each form: `$83,800.00`, `8380000`, `83800.00` (one per fixture transaction). Every non-empty line is `json.loads`-able with keys a subset of `{transaction_id, alert_key, outcome, attempts, latency_ms}`.
- **Fixtures:** the loopback fake server from T3 (shared via `conftest.py`); a fake consumer recording `commit` calls.

### T6 - tests/egress_check.py (new; CI tool run inside containers, not collected by pytest)
- **FR/NFR:** NFR-008 AC-1, AC-6, AC-8; FR-010.5 AC-5; US-028 AC-1/AC-5; US-029 AC-3.
- **Test description:** about 20 lines of stdlib (`argparse`, `socket`).
  - `--deny host:port` (repeatable): `socket.create_connection((h, p), timeout=3)`. It must raise `OSError` (DNS failure, unreachable or timeout all count as blocked). A success prints `LEAK host:port` and exits 1.
  - `--allow host:port` (repeatable): must succeed, else exit 1 (the positive control proves the probe ran on a working network).
  - It prints one line per probe (`blocked`/`reachable`) and exits 0 only if all expectations hold.
  - No data is sent on connected sockets; they are closed immediately.
- **Fixtures:** none. It runs in any app-image container (C4 copies `tests/`).

### T7 - tests/compose_check.py (new; host-side CI tool, reads `docker compose config --format json` on stdin)
- **NFR:** NFR-008 AC-2, AC-7, AC-8 (network half), NFR-008.2; ADR-028/029/030; US-028 AC-2/AC-5.
- **Test description:** argument `base` or `anthropic`. It asserts:
  - top-level `networks.internal.internal is True`, and `ingress`/`egress` are not internal;
  - no service is attached to `default` or to any network outside the three;
  - `postgres`, `redis`, `kafka`, `topic`, `migrate`, `scorer`, `ingest` and `llm` have networks == {internal}; `investigator` has {internal} in `base` and {internal, egress} in `anthropic`;
  - `api` networks == {internal, ingress}, and every `ports` entry has `host_ip == "127.0.0.1"`; no other service has `ports`;
  - `watchlist-fetch`: networks == {egress}, `profiles == ["fetch"]`, no `secrets`, exactly one volume, a bind with target `/app/watchlists`;
  - `llm`: `profiles == ["local"]`, no `ports`, no `secrets`, no `volumes`; the `FROM` line in `llm.Dockerfile` contains `@sha256:`;
  - investigator `environment.LLM_MODEL` is empty, and `DATA_CLASSIFICATION` is empty in both variants;
  - the investigator has no `anthropic_api_key` secret in `base`, and has it in `anthropic`;
  - api, scorer: `./watchlists` mounted `read_only`.
  - The first failure exits 1 with a precise message.
- **Fixtures:** none. It runs with the runner's `python3` (stdlib `json`, `sys`) and also works locally on Windows.

### T8 - tests/test_egress_static.py (new, pure, collected by pytest)
- **NFR:** NFR-008 AC-5; ARCH-001 B18 (RR-23 control).
- **Test description:** use `ast` to parse each file, from `/app` in the container (the repo root locally).
  - For `api.py`, `pipeline.py`, `scoring.py`, `kyc.py`, `rules.py`: no `Import`/`ImportFrom` whose top-level module is in {`urllib`, `requests`, `httpx`, `socket`, `http`, `aiohttp`, `anthropic`, `ssl`, `ftplib`, `smtplib`}. This also covers function-local imports, because it is an AST walk.
  - For `watchlist.py`: no import of `psycopg`, `pipeline`, `redis`, `confluent_kafka`, `quixstreams`, `kyc` or `scoring`. Every `urlopen` call has exactly one positional argument and no `data` keyword, and no `Request(` call exists (GET only).
- **Fixtures:** none.

## Ordering and Dependencies
1. The code author (C1-C13) and the test author (T1-T8) run **in parallel**. Both work from this plan, CS-008/009/010 and DI-010/011, and both first reconcile the drafts listed in Existing work-in-progress.
2. Code order:
   - C9, C4 (image);
   - C2 + C12 + C13 (compose topology; verify the telemetry flag and the override merge with `docker compose config`);
   - C1, C3;
   - C6;
   - C5 (LocalLLM, params);
   - C7 (config split, gate, data_classification, logging);
   - C8;
   - C10, C11 last.
3. Test order: T1, T7 and T8 first (they gate topology early and need no code from C5-C8), then T2, T3, T4, T5, T6.
4. **Code reviewer runs**, in order:
   - both `compose_check.py` variants;
   - `docker compose up --build -d`;
   - pytest (`-v`);
   - migrate a second time;
   - the egress probes (investigator, scorer, watchlist-fetch);
   - the telemetry check;
   - seed;
   - `latency.py`;
   - the AML-1042 drafted-row check;
   - the benchmark.

   They read the diff against the AC tables above. The `local-model` job is run once manually (`workflow_dispatch`) before Verify, and its result is attached as evidence.

## Build & Test Verification
- Build command: `docker compose up --build -d` (from CLAUDE.md). Local mode: `docker compose --profile local build llm`.
- Test command: `docker compose run --rm --entrypoint python ingest -m pytest -v` (from CLAUDE.md).
- Static checks: `docker compose --profile fetch --profile local config --format json | python tests/compose_check.py base`, and the same with `-f compose.yaml -f compose.anthropic.yaml ... anthropic`.
- Stack checks:
  - `docker compose exec -T investigator python tests/egress_check.py --deny api.anthropic.com:443 --allow postgres:5432` (and the same for scorer);
  - `docker compose --profile fetch run --rm --no-deps --entrypoint python watchlist-fetch tests/egress_check.py --deny postgres:5432`;
  - the telemetry `rpk` check;
  - `migrate` twice, `ingest seed`, `latency.py`, `ingest benchmark --seconds 60`.
- Lint command: none configured (CLAUDE.md).
- Expected:
  - all existing tests (test_rules, test_kyc, test_database) still pass, and all new tests pass;
  - a stub AML-1042 drafted row exists with `data_classification = customer`;
  - every probe gives the expected blocked/reachable result;
  - the push job stays under 15 min.

## Risk Assessment
- **High-impact files.**
  - `compose.yaml` and `Dockerfile` affect every service. A missing `networks:` on one service silently attaches it to `default`, which T7 catches.
  - `llm.complete_with_retry` is shared by all three backends; changing its retry classification affects anthropic (T3 covers both).
  - `watchlist.normalize` is shared by screening and grounding.
- **Internal network side effects.**
  - Nothing on `internal` can reach the internet at runtime: no `pip install` or `rpk` cloud calls at start.
  - Image pulls are done by the engine (NFR-008.3(d)). Redpanda may log blocked telemetry attempts until the explicit disable lands.
  - The pytest container (`ingest`) can no longer reach external hosts; no existing test needs that (verified: tests use `postgres`, `kafka` and `api` only).
- **Port publishing with mixed networks.** api is on an internal plus a bridge network; publishing works via the bridge. The CI readiness curl verifies it. If Docker picks the wrong gateway on some engine, set `networks: {ingress: {priority: 10}, internal: {}}` (verify only if the curl fails).
- **Profiles.** `docker compose up` never starts `llm` or `watchlist-fetch`. `docker compose config` must be run with `--profile fetch --profile local` to render them for T7. Nothing depends on a profiled service.
- **Backward compatibility.**
  - The OFAC command changes (C11).
  - The compose `LLM_MODEL` default is removed, so anthropic users must set `DATA_CLASSIFICATION=synthetic` and use the override.
  - Existing `pg-data` volumes keep working (migrate re-runs 004). Existing containers must be recreated to get the new networks (`docker compose up -d` does this).
- **Telemetry flag uncertainty.** The flag differs by Redpanda version. C2 requires verification, and the CI step checks the effective value rather than the flag spelling.
- **Ollama non-root and image size.** RR-25 may stay open. The image is several GB, which is why it sits behind a profile and why its CI job is opt-in. Small models fail grounding more often, so expect more `skipped` rows in local mode (by design).
- **Platform.** README commands stay PowerShell. `compose_check.py` runs under Windows Python too. On Linux hosts, `./watchlists` must be writable by uid 10001 for `watchlist-fetch`.
- **CI budget.** The push job adds less than 1 min. The local-model job is isolated, with its own 30-min limit.

## New Requirements (if any)
No new FR/US: FR-009/010/011, NFR-008 and US-016..US-029 cover every behavior here. Wording follow-ups for Requirements Sync (no new ids, so `proposes_new_requirements: []`):
- **NFR-008.3(c):** widen "Image build (`pip install` in the Dockerfile)" to also name the build-time model-weights download in `llm.Dockerfile` (ADR-029 already sanctions baked weights).
- **On completion:**
  - fill `source_files`/`test_files` for FR-009/010/011, NFR-008, US-021, US-028, US-029;
  - note in NFR-008/US-029 that AC-6 evidence comes from the opt-in `local-model` workflow;
  - record the actual Ollama digest, model tag/digest and Redpanda telemetry setting in DI-011 / ARCH-001 B19.

## Open Questions
1. **Default local model (`OLLAMA_MODEL` build arg).** The plan needs one small instruct model good at JSON output, e.g. `qwen2.5:3b` (about 2 GB). The choice affects image size, grounding pass rate and the `local-model` job time. Default if unanswered: `qwen2.5:3b`. Whichever is chosen, set `LLM_MODEL` to the same tag.
2. **Telemetry disable location.** The `kafka` command flag (ADR-028 wording) is preferred. The fallback is `rpk cluster config set` in the `topic` one-shot, if v24.3.10 ignores start-time cluster properties. Default: whichever the code author verifies works, recorded in README.
3. **`llm` behind profile `local`.** Confirm this is acceptable (it keeps the default `up` and CI fast; membership is unchanged). The alternative, always-on `llm`, makes every `up` build a multi-GB image.
4. **Stack-test privileges (carried from PLAN-001).** Superuser plus `SET ROLE aml_investigator` in the `ingest` container, with no secret mounted into `ingest`. Default: SET ROLE.
5. **Plan date.** `created` is set to 2026-11-24 so it post-dates the Define/Design re-sign-off recorded in `sdlc-metadata.yml`. The environment clock reads 2026-11-23. Adjust if the project calendar differs.

## Clarifications
