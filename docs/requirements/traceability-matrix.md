# Traceability Matrix — AML-KYC-Agent v0.3.0

Requirement → user stories → verifying tests, taken from the front matter of `functional/`, `nonfunctional/` and `user-stories/`. "Gap" means no automated check covers the behavior. "CI tool" means a script run by a workflow step (`tests/egress_check.py`, `tests/compose_check.py`), not collected by pytest.

## Functional requirements

| FR | Title | Status | Priority | User stories | Verification |
|---|---|---|---|---|---|
| FR-001 | Replay-safe transaction ingestion | implemented | P0 | US-001, US-011 | tests/test_database.py, tests/test_rules.py, `ingest benchmark` |
| FR-002 | Real-time rule scoring | implemented | P0 | US-002, US-010 | tests/test_rules.py, latency.py |
| FR-003 | Event-time velocity counters | implemented | P1 | US-003 | tests/test_rules.py (rule thresholds only) |
| FR-004 | Alert publication and decision audit | implemented | P0 | US-004, US-012 | latency.py |
| FR-005 | KYC onboarding review | implemented | P0 | US-005, US-006, US-013 | tests/test_kyc.py |
| FR-006 | Sanctions name screening with versioned snapshots | implemented | P0 | US-007 | tests/test_kyc.py |
| FR-007 | Outbound counterparty screening | implemented | P1 | US-008, US-013 | tests/test_kyc.py |
| FR-008 | Read API | implemented | P1 | US-009 | CI `/alerts` check (.github/workflows/ci.yml:13) |
| FR-009 | Alert investigation agent | implemented | P0 | US-016, US-017, US-018, US-019, US-020, US-027, US-028 | tests/test_investigator.py, tests/test_eval_scenarios.py, CI drafted-row check |
| FR-010 | Model provider switch | implemented | P0 | US-021, US-022, US-028, US-029 | tests/test_llm.py, tests/test_investigator.py, tests/test_eval_scenarios.py; FR-010.5 AC-6 opt-in `local-model` job only |
| FR-011 | Hallucination and grounding controls | implemented | P0 | US-023, US-024, US-025, US-026 | tests/test_grounding.py, tests/test_eval_scenarios.py, tests/test_llm.py |

## Non-functional requirements

| NFR | Title | Focus track | Priority | Verification | Tests | User stories |
|---|---|---|---|---|---|---|
| NFR-001 | Ingestion throughput and alert latency | quality | P0 | benchmark | latency.py, `ingest benchmark` | US-002, US-010, US-011 |
| NFR-002 | Replay-safe, idempotent processing | quality | P0 | test | tests/test_database.py, tests/test_kyc.py | US-001, US-003, US-006, US-018, US-020 |
| NFR-003 | Least privilege and append-only audit | security | P0 | code-review | tests/test_investigator.py (Phase 4 role `aml_investigator` only; `aml_worker` still a gap) | US-009, US-012, US-027 |
| NFR-004 | Versioned, reproducible decision audit trail | quality | P0 | test | tests/test_database.py, tests/test_kyc.py | US-004, US-005, US-007, US-008, US-012, US-016, US-017, US-023, US-024, US-026 |
| NFR-005 | Automated components recommend only | security | P0 | code-review | tests/test_investigator.py (test_stack_scored_and_alerted_unchanged; Phase 4 only; screeners still a gap) | US-013, US-019, US-024, US-025 |
| NFR-006 | Synthetic data only; no credentials by default | security | P0 | test | tests/test_rules.py, tests/test_kyc.py, tests/test_investigator.py, CI migrate-log password check | US-014, US-021, US-022, US-026 |
| NFR-007 | Docker Compose portability and CI budget | quality | P1 | ci-matrix | tests/test_database.py, .github/workflows/ci.yml | US-015, US-022 |
| NFR-008 | Customer data stays inside the deployment | security | P0 | test | tests/test_investigator.py, tests/test_egress_static.py, CI tools tests/egress_check.py + tests/compose_check.py; AC-6 opt-in `local-model` job only | US-021, US-028, US-029 |

## User stories → tests

| Tests | User stories |
|---|---|
| tests/test_database.py | US-001 |
| tests/test_rules.py | US-002, US-003 |
| tests/test_kyc.py | US-005, US-006, US-007, US-008 |
| latency.py | US-004, US-010 |
| tests/test_investigator.py | US-016, US-017, US-018, US-019, US-020, US-021, US-022, US-023, US-024, US-025, US-027, US-028, US-029 |
| tests/test_llm.py | US-020, US-022, US-023, US-029 |
| tests/test_grounding.py | US-016, US-019, US-023, US-025 |
| tests/test_eval_scenarios.py, tests/eval/scenarios.json | US-016, US-020, US-026, US-027 |
| CI tools tests/egress_check.py, tests/compose_check.py (`.github/workflows/ci.yml`) | US-026 AC-4, US-028 AC-1, AC-2, AC-5 |
| opt-in `local-model` job | US-029 AC-3 (and the real-server half of AC-1) |
| no test yet (gap) | US-009, US-011, US-012, US-013, US-014, US-015 |

## Known gaps

- FR-001.2 / US-001 AC-2: committing the offset after the DB commit has no test (the CI benchmark only exercises it end to end).
- FR-001.3 AC-1: rejection of a direct duplicate `transaction.recorded` insert is untested.
- FR-002.3 / FR-002.4: the scorer's replay reuse and 48 h scored-history query are untested.
- FR-002.1 / FR-003.4: below-threshold values are untested; only at-threshold values are checked.
- FR-003: the Redis velocity script (retry counted once, 48 h retention) has no test.
- FR-004.1 / US-004 AC-1, AC-3: the `scored.v1` / `alerted.v1` audit writes have no direct test; latency.py checks only the published alert.
- FR-005.1: no validation (422) tests.
- FR-006.1 / FR-006.5: SDN parse errors, snapshot caching and the `SDN_FILE` switch are untested.
- FR-007.1 / FR-007.4: the debits-only and recording-only behavior of payment screening is untested.
- US-007 AC-3, US-008 AC-2: the recorded snapshot hash isn't asserted.
- FR-008 / US-009: `GET /alerts` has only the CI curl check; `GET /scores/{id}` (including the 404) is untested.
- NFR-003 / US-012: no test asserts that `aml_worker` UPDATE/DELETE and INSERT into `cases` are denied.
- NFR-005 / US-013: no test asserts that screeners never block or close a case.
- FR-009: onboarding KYC findings can't be linked to an account, so the agent uses `payment.screened.v1` evidence only. This is a stated limitation.
- NFR-008 AC-6 / FR-010.5 AC-6 / US-029 AC-3: verified only by the opt-in `local-model` workflow_dispatch job (not run on push). The network half is covered on every push by NFR-008 AC-1 (CI probe) and `tests/compose_check.py`. Unverified until the job is dispatched.
- FR-010.5 AC-5, NFR-008 AC-1/AC-2/AC-7/AC-8, US-028 AC-1/AC-2/AC-5: covered by CI tools, not pytest, so they do not run in the local `pytest` command.
- US-026 AC-3 / FR-011.5 AC-3: the real-model rate report (`eval_investigator.py`) has no automated test; only its refusal gate is tested.
- `llm` container runs as non-root uid 10001: not asserted (RR-25).
- FR-009.1 AC-2 / FR-010.5 AC-4: the `consume()` offset-commit helper is covered through FR-009.1 AC-2 and FR-010.5 AC-4 tests, but the real Kafka commit (confluent consumer) is faked in tests.
- Phase 4 additions deliberately NOT given new ids (PLAN-002 `proposes_new_requirements: []`): the CI check that the migrate log never contains the DB password (covered by NFR-006 and CS-010), and the `consume()` commit helper (covered by FR-009.1 and FR-010.4). No duplicates minted.
