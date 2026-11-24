---
id: "TRACE-DESIGN-001"
title: "Design Traceability Matrix"
type: "traceability"
status: "draft"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
---

# Design Traceability Matrix

Generated from the front matter of `component-specs/`, `dependency-interfaces/` and `adrs/`. ADR-017..027 were accepted at the Design sign-off (2026-11-23, per adrs/README.md); ADR-028..030 (NFR-008 delta) were accepted at the Design sign-off (2026-11-24). CS-008/009/010, DI-010 and DI-011 describe Phase 4 code, built under PLAN-002 (Requirements Sync 2026-11-24; FR-009/010/011 implemented). Design-gate amendments: FR-010.3 and NFR-006 were amended at Design to match ADR-021 (secret files); ADR-014 facts were corrected (initdb mounts all of `./sql`, so 001-003 run at initdb on a fresh volume; migrate re-runs 002-003) and carries a proposed Phase 4 amendment (initdb mounts only 001, migrate runs 002-004, see ADR-018); the Phase 4 D9 rule (no Kafka publish, no cases, async) moved from ADR-016 to proposed ADR-017.

## 1. FR -> CS/DI -> ADR -> source -> tests

| FR | Title | CS | DI | Constraining ADRs | Source | Tests |
|---|---|---|---|---|---|---|
| FR-001 | Replay-safe transaction ingestion | CS-001, CS-007 | DI-001, DI-002 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-009, ADR-013, ADR-014, ADR-015, ADR-017, ADR-018, ADR-024, ADR-026 | pipeline.py, sql/001-003 | tests/test_database.py, tests/test_rules.py, `ingest benchmark` |
| FR-002 | Real-time rule scoring | CS-002, CS-003, CS-007 | DI-002, DI-003, DI-006 | ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-013, ADR-014, ADR-016, ADR-018, ADR-024 | scoring.py, rules.py, sql/001-003 | tests/test_rules.py, latency.py |
| FR-003 | Event-time velocity counters | CS-002, CS-003 | DI-003, DI-006 | ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-013, ADR-016 | scoring.py, rules.py | tests/test_rules.py (thresholds only) |
| FR-004 | Alert publication and decision audit | CS-001, CS-002, CS-007 | DI-001, DI-003 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-013, ADR-014, ADR-015, ADR-016, ADR-017, ADR-024, ADR-026 | pipeline.py, scoring.py, sql/001-003 | latency.py |
| FR-005 | KYC onboarding review | CS-004, CS-005, CS-006, CS-007 | DI-002, DI-004, DI-005, DI-007, DI-009 | ADR-003, ADR-004, ADR-009, ADR-010, ADR-011, ADR-012, ADR-013, ADR-014, ADR-015, ADR-016, ADR-018, ADR-019, ADR-024, ADR-026 | kyc.py, watchlist.py, api.py, sql/001-003 | tests/test_kyc.py |
| FR-006 | Sanctions name screening with versioned snapshots | CS-004, CS-005 | DI-007, DI-008 | ADR-003, ADR-004, ADR-009, ADR-010, ADR-011, ADR-013, ADR-015, ADR-016 | kyc.py, watchlist.py | tests/test_kyc.py |
| FR-007 | Outbound counterparty screening | CS-002, CS-004, CS-005, CS-007 | DI-002, DI-007 | ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-010, ADR-011, ADR-013, ADR-014, ADR-015, ADR-016, ADR-018, ADR-024 | scoring.py, kyc.py, watchlist.py, sql/001-003 | tests/test_kyc.py |
| FR-008 | Read API | CS-006 | DI-002, DI-004, DI-005, DI-009 | ADR-003, ADR-004, ADR-009, ADR-012, ADR-013, ADR-015, ADR-016, ADR-018, ADR-019, ADR-026 | api.py | CI `/alerts` curl (.github/workflows/ci.yml) |
| FR-009 | Alert investigation agent | CS-008, CS-009, CS-010 | DI-001, DI-002, DI-009, DI-010, DI-011 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-013, ADR-014, ADR-016, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026, ADR-027, ADR-028, ADR-029, ADR-030 | investigator.py, llm.py, grounding.py, sql/004-investigation.sql | tests/test_investigator.py, tests/test_eval_scenarios.py |
| FR-010 | Model provider switch | CS-008, CS-009 | DI-010, DI-011 | ADR-002, ADR-005, ADR-016, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-025, ADR-026, ADR-027, ADR-028, ADR-029, ADR-030 | investigator.py, llm.py, eval_investigator.py, llm.Dockerfile, compose.yaml, compose.anthropic.yaml | tests/test_llm.py, tests/test_investigator.py; CI tools egress_check/compose_check; FR-010.5 AC-6 opt-in `local-model` job |
| FR-011 | Hallucination and grounding controls | CS-008, CS-009, CS-010 | — | ADR-002, ADR-005, ADR-014, ADR-016, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026, ADR-027, ADR-030 | grounding.py, investigator.py, llm.py, eval_investigator.py, tests/eval/scenarios.json | tests/test_grounding.py, tests/test_eval_scenarios.py |

## 2. NFR -> CS/DI -> ADR (satisfies_nfr) -> tests

| NFR | Title | CS/DI documents | ADRs satisfying it | Tests |
|---|---|---|---|---|
| NFR-001 | Ingestion throughput and alert latency | CS-001, CS-002, CS-003, DI-001, DI-003, DI-006, DI-007 | ADR-001, ADR-002, ADR-006, ADR-007, ADR-008, ADR-011, ADR-017 | latency.py, `ingest benchmark` |
| NFR-002 | Replay-safe, idempotent processing | CS-001, CS-002, CS-004, CS-006, CS-007, CS-008, CS-010, DI-001, DI-002, DI-003, DI-006 | ADR-002, ADR-004, ADR-005, ADR-006, ADR-007, ADR-014, ADR-017, ADR-023 | tests/test_database.py, tests/test_kyc.py |
| NFR-003 | Least privilege and append-only audit | CS-006, CS-007, CS-008, CS-010, DI-002, DI-004 | ADR-003, ADR-012, ADR-018, ADR-024, ADR-026 | tests/test_investigator.py (Phase 4 role only; `aml_worker` gap) |
| NFR-004 | Versioned, reproducible decision audit trail | CS-001, CS-002, CS-003, CS-004, CS-005, CS-006, CS-007, CS-008, CS-010, DI-002, DI-007, DI-008 | ADR-003, ADR-008, ADR-009, ADR-010, ADR-011, ADR-020, ADR-022, ADR-023, ADR-024, ADR-025, ADR-027 | tests/test_database.py, tests/test_kyc.py |
| NFR-005 | Automated components recommend only | CS-004, CS-008, CS-009, CS-010, DI-010, DI-011 | ADR-016, ADR-017, ADR-018, ADR-019, ADR-022, ADR-027, ADR-029, ADR-030 | tests/test_investigator.py (Phase 4 only; screeners gap) |
| NFR-006 | Synthetic data only; no credentials by default | CS-001, CS-004, CS-005, CS-008, CS-009, CS-010, DI-001, DI-002, DI-004, DI-008, DI-009, DI-010, DI-011 | ADR-010, ADR-012, ADR-013, ADR-015, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-025, ADR-026, ADR-028, ADR-029, ADR-030 | tests/test_rules.py, tests/test_kyc.py |
| NFR-007 | Docker Compose portability and CI budget | CS-001, CS-008, CS-009, DI-005, DI-010 | ADR-001, ADR-013, ADR-014, ADR-022 | CI workflow, tests/test_database.py |
| NFR-008 | Customer data stays inside the deployment | CS-005, CS-006, CS-008, CS-009, DI-011 | ADR-028, ADR-029, ADR-030 | docker compose config (AC-2, AC-7), tests/test_investigator.py load_config (AC-3), log assertion (AC-4), grep review (AC-5), in-container checks (AC-1, AC-6, AC-8; planned) |

## 3. CS -> FR coverage

| CS | Title | satisfies_fr | satisfies_nfr |
|---|---|---|---|
| CS-001 | Pipeline: ingest, produce, record_transaction | FR-001, FR-004 | NFR-001, NFR-002, NFR-004, NFR-006, NFR-007 |
| CS-002 | Scorer: Quix streaming scoring pipeline | FR-002, FR-003, FR-004, FR-007 | NFR-001, NFR-002, NFR-004 |
| CS-003 | Rules: pure risk assessment | FR-002, FR-003 | NFR-001, NFR-004 |
| CS-004 | KYC: onboarding review and payment screening | FR-005, FR-006, FR-007 | NFR-002, NFR-004, NFR-005, NFR-006 |
| CS-005 | Watchlist: SDN parsing and fuzzy screening | FR-005, FR-006, FR-007 | NFR-004, NFR-006, NFR-008 |
| CS-006 | Read API and onboarding endpoint | FR-005, FR-008 | NFR-002, NFR-003, NFR-004, NFR-008 |
| CS-007 | SQL migrations 001-003 (schema and grants) | FR-001, FR-002, FR-004, FR-005, FR-007 | NFR-002, NFR-003, NFR-004 |
| CS-008 | Investigator: alert investigation agent (PROPOSED, Phase 4) | FR-009, FR-010, FR-011 | NFR-002, NFR-003, NFR-004, NFR-005, NFR-006, NFR-007, NFR-008 |
| CS-009 | LLM provider switch: stub, local and Anthropic (PROPOSED, Phase 4) | FR-010, FR-009, FR-011 | NFR-005, NFR-006, NFR-007, NFR-008 |
| CS-010 | Migration sql/004-investigation.sql (PROPOSED, Phase 4) | FR-009, FR-011 | NFR-002, NFR-003, NFR-004, NFR-005, NFR-006 |

## 4. DI -> FR mapping

| DI | Title | satisfies_fr | satisfies_nfr |
|---|---|---|---|
| DI-001 | confluent-kafka (Kafka client; Redpanda broker) | FR-001, FR-004, FR-009 | NFR-001, NFR-002, NFR-006 |
| DI-002 | psycopg 3 (PostgreSQL client; PostgreSQL server) | FR-001, FR-002, FR-005, FR-007, FR-008, FR-009 | NFR-002, NFR-003, NFR-004, NFR-006 |
| DI-003 | Quix Streams (stream processing) | FR-002, FR-003, FR-004 | NFR-001, NFR-002 |
| DI-004 | FastAPI (HTTP API framework) | FR-005, FR-008 | NFR-003, NFR-006 |
| DI-005 | uvicorn (ASGI server) | FR-008, FR-005 | NFR-007 |
| DI-006 | redis-py (Redis client; Redis server) | FR-003, FR-002 | NFR-001, NFR-002 |
| DI-007 | RapidFuzz (fuzzy name matching) | FR-005, FR-006, FR-007 | NFR-001, NFR-004 |
| DI-008 | defusedxml (safe XML parsing) | FR-006 | NFR-006, NFR-004 |
| DI-009 | pydantic v2 (validation) | FR-005, FR-008, FR-009 | NFR-006 |
| DI-010 | Anthropic API and Python SDK (PROPOSED, Phase 4) | FR-010, FR-009 | NFR-005, NFR-006, NFR-007 |
| DI-011 | Local model server HTTP API, Ollama (PROPOSED, Phase 4) | FR-010, FR-009 | NFR-005, NFR-006, NFR-008 |

## 5. ADR -> NFR mapping

| ADR | Title | Status | Satisfies NFR | Constrains |
|---|---|---|---|---|
| ADR-001 | Redpanda as the Kafka broker | accepted | NFR-001, NFR-007 | CS-001, DI-001 |
| ADR-002 | Account-keyed single-partition topics | accepted | NFR-001, NFR-002 | CS-001, CS-002, CS-008, DI-001, DI-003 |
| ADR-003 | Postgres audit table as system of record, append-only via grants | accepted | NFR-003, NFR-004 | CS-001, CS-002, CS-004, CS-006, CS-007, DI-002 |
| ADR-004 | Idempotency via uuid5 ids, ON CONFLICT and partial unique indexes | accepted | NFR-002 | CS-001, CS-002, CS-004, CS-007, DI-002 |
| ADR-005 | Kafka offset commit after DB commit | accepted | NFR-002 | CS-001, CS-002, CS-008, DI-001, DI-003 |
| ADR-006 | Quix Streams for the scorer, confluent_kafka for ingest | accepted | NFR-001, NFR-002 | CS-001, CS-002, DI-001, DI-003 |
| ADR-007 | Redis Lua event-time velocity windows | accepted | NFR-001, NFR-002 | CS-002, DI-006 |
| ADR-008 | Pure rules engine | accepted | NFR-001, NFR-004 | CS-002, CS-003 |
| ADR-009 | Versioned audit action names | accepted | NFR-004 | CS-001, CS-002, CS-003, CS-004, CS-006, CS-007 |
| ADR-010 | defusedxml parsing with SHA-256 SDN snapshots | accepted | NFR-004, NFR-006 | CS-004, CS-005, DI-008 |
| ADR-011 | RapidFuzz threshold 88 with token-sorted normalization | accepted | NFR-001, NFR-004 | CS-004, CS-005, DI-007 |
| ADR-012 | FastAPI on loopback, no authentication | accepted | NFR-003, NFR-006 | CS-006, DI-004, DI-005 |
| ADR-013 | Hard-coded configuration, SDN_FILE the only environment variable | accepted | NFR-006, NFR-007 | CS-001, CS-002, CS-005, CS-006, DI-002 |
| ADR-014 | Idempotent migrations re-run on every startup (facts corrected; Phase 4 amendment proposed via ADR-018) | accepted | NFR-002, NFR-007 | CS-001, CS-007, CS-010 |
| ADR-015 | Synthetic data only | accepted | NFR-006 | CS-001, CS-004, CS-005, CS-006 |
| ADR-016 | Recommend-only posture (D9 Phase 4 rule moved to ADR-017) | accepted | NFR-005 | CS-002, CS-004, CS-006, CS-008 |
| ADR-017 | Investigator process model (owns D9 recommend-only rule) | accepted | NFR-001, NFR-002, NFR-005 | CS-008, DI-001 |
| ADR-018 | Dedicated aml_investigator role, investigator_audit view and two-way insert guard trigger | accepted | NFR-003, NFR-005, NFR-006 | CS-008, CS-010, DI-002 |
| ADR-019 | Untrusted-input and output handling for the model call | accepted | NFR-005, NFR-006 | CS-008, CS-009, DI-009 |
| ADR-020 | Data minimization allow-list, SUBJECT_ACCOUNT alias and stored payload hash | accepted | NFR-004, NFR-006 | CS-008, CS-009 |
| ADR-021 | Secrets via Docker secret files with env fallback and sanitized errors | accepted | NFR-006 | CS-008, CS-009, DI-010 |
| ADR-022 | Anthropic SDK, exact pin, own retry, deterministic parameters and recorded versions | accepted | NFR-004, NFR-005, NFR-006, NFR-007 | CS-008, CS-009, DI-010 |
| ADR-023 | Draft/skip mutual exclusion via combined partial unique index | accepted | NFR-002, NFR-004 | CS-008, CS-010 |
| ADR-024 | Audit immutability triggers blocking UPDATE, DELETE and TRUNCATE | accepted | NFR-003, NFR-004 | CS-007, CS-010 |
| ADR-025 | Audit retention of at least five years, no deletion path, residual-risk register | accepted | NFR-004, NFR-006 | CS-008, CS-010 |
| ADR-026 | Non-root container user for all services | accepted | NFR-003, NFR-006 | CS-001, CS-006, CS-008, DI-005 |
| ADR-027 | Hallucination and grounding controls for drafted narratives | accepted | NFR-004, NFR-005 | CS-008, CS-009, CS-010 |
| ADR-028 | Network segmentation and closed egress list | accepted | NFR-006, NFR-008 | CS-005, CS-006, CS-008, DI-011 |
| ADR-029 | Self-hosted model backend (LLM_MODE=local) | accepted | NFR-005, NFR-006, NFR-008 | CS-008, CS-009, DI-011 |
| ADR-030 | Synthetic-data gate for the external model provider | accepted | NFR-005, NFR-006, NFR-008 | CS-008, CS-009 |

## 6. Component -> ADR constraints

| CS/DI | constrained_by_adrs |
|---|---|
| CS-001 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-009, ADR-013, ADR-014, ADR-015, ADR-026 |
| CS-002 | ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-013, ADR-016 |
| CS-003 | ADR-008, ADR-009 |
| CS-004 | ADR-003, ADR-004, ADR-009, ADR-010, ADR-011, ADR-015, ADR-016 |
| CS-005 | ADR-010, ADR-011, ADR-013, ADR-015, ADR-028 |
| CS-006 | ADR-003, ADR-009, ADR-012, ADR-013, ADR-015, ADR-016, ADR-026, ADR-028 |
| CS-007 | ADR-003, ADR-004, ADR-009, ADR-014, ADR-024 |
| CS-008 | ADR-002, ADR-005, ADR-016, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022, ADR-023, ADR-025, ADR-026, ADR-027, ADR-028, ADR-029, ADR-030 |
| CS-009 | ADR-019, ADR-020, ADR-021, ADR-022, ADR-027, ADR-029, ADR-030 |
| CS-010 | ADR-014, ADR-018, ADR-023, ADR-024, ADR-025, ADR-027 |
| DI-001 | ADR-001, ADR-002, ADR-005, ADR-006, ADR-017 |
| DI-002 | ADR-003, ADR-004, ADR-013, ADR-018 |
| DI-003 | ADR-002, ADR-005, ADR-006 |
| DI-004 | ADR-012 |
| DI-005 | ADR-012, ADR-026 |
| DI-006 | ADR-007 |
| DI-007 | ADR-011 |
| DI-008 | ADR-010 |
| DI-009 | ADR-019 |
| DI-010 | ADR-021, ADR-022 |
| DI-011 | ADR-019, ADR-020, ADR-022, ADR-028, ADR-029 |

## 7. Verification and coverage gaps

- Every FR-001..FR-010 appears in at least one CS `satisfies_fr`: PASS. FR-011 is covered by CS-008, CS-009 and CS-010 (CS-008 specifies the evaluation set).
- Every NFR-001..NFR-008 appears in at least one CS/DI `satisfies_nfr` and at least one ADR: PASS.
- ADR status: ADR-001..016 accepted (retroactive); ADR-017..027 accepted at the Design sign-off; ADR-028..030 accepted at the Design sign-off 2026-11-24 (NFR-008 delta). No ADR is superseded; none conflicts with an existing ADR (the `adrs/` folder was empty).
- Gaps found: no script was run for this matrix; it was cross-checked by hand against CS-008 frontmatter (ADR-016 added to CS-008 in sections 5 and 6).

Remaining gaps and notes:
1. NFR-003 and NFR-005 have an automated test only for the Phase 4 investigator role (tests/test_investigator.py); the Phase 1-3 `aml_worker` and screener parts have none (inherited from the requirements matrix). ADR-003, 016, 018, 024 depend on code review only until a grant-denial test and a no-block test exist.
2. FR-009/FR-010/FR-011 are built (PLAN-002). tests/test_investigator.py, tests/test_llm.py, tests/test_grounding.py, tests/test_eval_scenarios.py and tests/test_egress_static.py exist; `llm` uid 10001 is unasserted (RR-25).
3. ADR-005 evidence is `partial`: the scorer's commit timing is Quix behavior, not asserted in this repo.
4. ADR-009 records the versioned-action convention but `transaction.recorded` (pipeline.py:59) is unversioned.
5. Numbering mismatch: ARCH-001 uses R-01..R-16 labels, where R-12 is Loopback API, R-13 Synthetic data, R-14 Hard-coded config, R-15 Idempotent migrations. ADR IDs differ for three of them: R-13 -> ADR-015, R-14 -> ADR-013, R-15 -> ADR-014 (R-12 -> ADR-012, R-16 -> ADR-016). ARCH-001 section 9 now lists the decisions in ADR order with the R-label in parentheses (e.g. ADR-013 (R-14)), and the mapping note at the top of ARCH-001 gives the full R-to-ADR table. Sections of ARCH-001 other than 9 were also edited at Design, so section 9 was not left unchanged.
6. ADR-006's "Quix for the scorer" and ADR-017's Quix rejection are consistent: Quix for declarative stream transform, plain consumer where blocking calls need control.
7. Residual risks (ARCH-001 section 8, RR-1 onward) are owned by ADR-025; no separate ADR exists for the deferred controls (by design).
8. Design-gate amendments: (a) FR-010.3 and NFR-006 amended at Design to match ADR-021 (single DB password secret file, `ANTHROPIC_API_KEY_FILE`, committed `secrets/demo/` defaults, `.gitignore` additions); (b) ADR-014 corrected and given a proposed Phase 4 amendment (initdb mounts only 001; migrate runs 002-004); (c) ADR-016 no longer carries the Phase 4 D9 rule, which lives only in ADR-017; (d) ADR-018 trigger is two-way; (e) FR-009.7 names `audit_investigation_alert_once` (ADR-023); (f) ADR-009 line reference fixed to scoring.py:45.
9. W23 is closed for integrity: the DB partial unique indexes (ADR-023) enforce draft/skip exclusivity; only the duplicate model call cost remains (RR-14).
10. Code dependency direction: FR-009 -> FR-010 and FR-011; FR-010 and FR-011 are independent of each other. The FR `depends_on` cross-references are spec links, not build dependencies.

## 8. NFR-008 delta traceability (2026-11-23, PHASE 4, built under PLAN-002)

| Requirement / story | CS / DI | ADR | ARCH-001 / data-flow | Test |
|---|---|---|---|---|
| NFR-008.1 no outbound route for data-holding services | CS-008 (Deployment), CS-009 | ADR-028 | section 1a, B16, B18, RR-23 | tests/compose_check.py over `docker compose config` (AC-7, CI); tests/egress_check.py in-container connect (AC-1 CI; AC-6 opt-in `local-model` job only) |
| NFR-008.2 no host exposure except loopback api | CS-006 | ADR-028 | section 1a, B18 | tests/compose_check.py (AC-2, CI) |
| NFR-008.3 closed egress list: (a) anthropic synthetic only | CS-008, CS-009 | ADR-030 | B12, RR-24, data-flow 2a | tests/test_investigator.py load_config/main tests (AC-3) |
| NFR-008.3 (b) OFAC fetch, (d) image pulls, (e) api loopback | CS-005, CS-006 | ADR-028 | B17, B18, RR-23, B9 | tests/compose_check.py + egress_check (AC-8, CI); tests/test_egress_static.py (AC-5) |
| NFR-008.3 (c) image build | — (build-time; no runtime component) | ADR-028 | B15 | review (build-time only); wording widened 2026-11-24 to cover the model-weights download in `llm.Dockerfile` (ADR-029) |
| NFR-008.4 agents do not forward data | CS-008 (Logging, Component Interactions: no publish, no file) | ADR-029, ADR-017 | B13, B16 | tests/test_investigator.py test_stack_logs_carry_no_evidence (AC-4) |
| NFR-008.5 development agents see synthetic data only | process control | ADR-015 | NFR-006 v1.2 scope, `secrets/demo/` only | review |
| FR-010.5 local mode (AC-1..AC-6) | CS-008, CS-009, DI-011 | ADR-029, ADR-028 | B16 | tests/test_llm.py, tests/test_investigator.py; AC-6 opt-in `local-model` job only |
| FR-010.6 synthetic gate (AC-1..AC-6) | CS-008 | ADR-030 | B12, data-flow 2a | tests/test_investigator.py |
| FR-011.5 AC-3 eval script gate | CS-008 (eval_investigator.py) | ADR-030, ADR-027 | B12 | tests/test_eval_scenarios.py test_eval_refuses_unless_anthropic_and_synthetic |
| US-028 customer data never leaves the deployment (FR-009, FR-010) | CS-008, CS-009, DI-011 | ADR-028, ADR-029, ADR-030 | section 1a, B12, B16-B18 | as NFR-008 ACs |
| US-029 self-hosted model (FR-010) | CS-009, DI-011 | ADR-029 | B16 | tests/test_investigator.py, tests/test_llm.py; AC-3 opt-in job only |

No orphans: every row above resolves to at least one ADR and one CS or DI, except NFR-008.5, which is a process control verified by review; ADR-028..030 each satisfy NFR-008. Remaining gap: NFR-008 AC-6 runs only in the opt-in `local-model` job; AC-1, AC-8 run as CI steps, not pytest.

## 9. FR Coverage (Requirements Sync, 2026-11-24, PLAN-002)

No new FR was minted by PLAN-002 (`proposes_new_requirements: []`), so no CS `satisfies_fr` list changed. Existing FR to CS links, now built:

| FR | Satisfied by CS | Notes |
|---|---|---|
| FR-009 | CS-008, CS-009, CS-010 | investigator.py, sql/004-investigation.sql |
| FR-010 | CS-008, CS-009 | llm.py (`StubLLM`, `LocalLLM`, `AnthropicLLM`), compose files |
| FR-011 | CS-008, CS-009, CS-010 | grounding.py, eval_investigator.py |

Spec amendments applied 2026-11-24 (versions bumped): CS-008 v1.3 and FR-010 v1.3 (env key fallback when the file is absent or empty), CS-010 v1.1 (`set_config` result suppressed; RR-15 unchanged), DI-010 v1.1 (`anthropic==1.17.0`, 2.x not adopted, ADR-022), NFR-008 v1.2 (3(c) widened to image build incl. model weights in `llm.Dockerfile`).
