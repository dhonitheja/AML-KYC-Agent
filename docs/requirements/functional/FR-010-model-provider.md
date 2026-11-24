---
id: "FR-010"
title: "Model provider switch"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.3"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["investigator.py", "llm.py", "eval_investigator.py", "llm.Dockerfile", "compose.yaml", "compose.anthropic.yaml", ".github/workflows/ci.yml", "requirements.txt"]
test_files: ["tests/test_investigator.py", "tests/test_llm.py", "tests/test_eval_scenarios.py", "tests/conftest.py", "tests/egress_check.py", "tests/compose_check.py"]
depends_on: ["FR-011"]
implements: []
---

# FR-010: Model provider switch (Phase 4, built)

## Description
Selects the model backend used by the investigation agent (FR-009). A deterministic stub is the default so tests and CI need no credentials. Every mode SHALL respect NFR-008: customer data never leaves the deployment. `local` keeps the model inside the deployment, and `anthropic` is allowed only for declared-synthetic deployments. Phase 4 introduces new env configuration on the `investigator` service only (ADR-013 amendment).

## Change notes
- v1.3 (2026-11-24, Requirements Sync, PLAN-002): promoted to implemented. FR-010.3 amended after code review: the `ANTHROPIC_API_KEY` env fallback applies when the key file is absent OR empty (the committed demo file is empty, so this is the only way the dev fallback is reachable); a non-empty file still wins (AC-6/AC-7/AC-8 reworded). Test: test_anthropic_empty_key_file_falls_back_to_env. FR-010.5 AC-6 is verified only by the opt-in `local-model` CI job.
- v1.2 (2026-11-23, NFR-008 delta): added `local` mode (FR-010.5, self-hosted model inside the deployment) and the synthetic-data gate for `anthropic` (FR-010.6, `DATA_CLASSIFICATION`); FR-010.1 and FR-010.3 config list extended; AC-5/AC-9 extended to local mode. Gate round 7: FR-010.3 AC-1/4/6/7/8 now state `DATA_CLASSIFICATION=synthetic`; FR-010.5 AC-6 added.
- v1.1: Defined skip reasons in FR-010.4 (model_failure vs grounding_failure, last-failed-attempt rule, FR-011.2); added FR-011 to depends_on; added key/secret/host precedence ACs to FR-010.3.

## Requirements

### FR-010.1: Mode selection
Env `LLM_MODE` SHALL select `stub` (default when unset), `local` (FR-010.5) or `anthropic` (FR-010.6). An unknown value SHALL fail fast at startup with a clear error.

**Acceptance Criteria:**
- AC-1: Unset env selects stub.
- AC-2: `LLM_MODE=bogus` exits non-zero at startup.
- AC-3: `LLM_MODE=local` is accepted (subject to FR-010.5 checks).

### FR-010.2: Deterministic stub
Stub mode SHALL make no network calls, need no credentials, and return identical output for identical evidence. It SHALL be the default in tests and CI (see NFR-006).

**Acceptance Criteria:**
- AC-1: Two calls with the same evidence return equal drafts.
- AC-2: Test suite passes with no API key and network disabled.

### FR-010.3: Real mode opt-in
Configuration SHALL be exactly these env vars: `LLM_MODE` (`stub` default | `local` | `anthropic`); `DATA_CLASSIFICATION` (`customer` default when unset | `synthetic`; see FR-010.6); `LOCAL_LLM_URL` (required when `LLM_MODE=local`, ignored otherwise; see FR-010.5); `ANTHROPIC_API_KEY_FILE` (default `/run/secrets/anthropic_api_key`), with `ANTHROPIC_API_KEY` accepted only as a local-development fallback when the file is absent or empty (a non-empty file always wins); the key is read only when `LLM_MODE=anthropic`, and startup fails fast if neither yields a key; `INVESTIGATOR_DB_PASSWORD_FILE` (default `/run/secrets/investigator_db_password`; required, with no fallback to the `aml_worker` DSN; it is the same secret file `migrate` uses to set the role password); `INVESTIGATOR_DB_HOST` (default `postgres`); `LLM_MODEL` (model id recorded in `audit.model_version`; default `claude-opus-5-5` when `LLM_MODE=anthropic` and `LLM_MODEL` is unset; required with no default when `LLM_MODE=local`; in stub mode `LLM_MODEL` is ignored and `model_version` is `stub-v1`); `LLM_TIMEOUT_SECONDS` (default 30); `LLM_MAX_ATTEMPTS` (default 3). The key SHALL never be written to audit, logs or the repo (NFR-006). `audit.prompt_version` SHALL record the prompt template version string (e.g. `investigation-prompt-v2`).

**Acceptance Criteria:**
- AC-1: `LLM_MODE=anthropic` with `DATA_CLASSIFICATION=synthetic` and no key fails at startup.
- AC-2: Audit rows from stub mode carry `model_version = "stub-v1"` and a non-null `prompt_version` (e.g. `investigation-prompt-v2`).
- AC-3: No audit row or log line contains the key.
- AC-4: With `LLM_MODE=anthropic`, `DATA_CLASSIFICATION=synthetic` and `LLM_MODEL` unset, `model_version` is `claude-opus-5-5`.
- AC-5: In stub mode, setting `LLM_MODEL` has no effect; `model_version` remains `stub-v1`.
- AC-6: In anthropic mode with `DATA_CLASSIFICATION=synthetic`, when the `ANTHROPIC_API_KEY_FILE` file is present and non-empty it is used even if the `ANTHROPIC_API_KEY` env var is also set.
- AC-7: In anthropic mode with `DATA_CLASSIFICATION=synthetic`, when the file is absent or empty and `ANTHROPIC_API_KEY` is set, the env value is used (development fallback).
- AC-8: In anthropic mode with `DATA_CLASSIFICATION=synthetic` and neither a non-empty file nor the env var, startup fails.
- AC-9: In stub mode and in local mode the API key (file or env) is never read.
- AC-10: A missing or empty `INVESTIGATOR_DB_PASSWORD_FILE` fails startup and never falls back to the `aml_worker` DSN.
- AC-11: With `INVESTIGATOR_DB_HOST` unset, the database host is `postgres`.

### FR-010.4: Bounded calls and failure behavior
In every mode, each model call SHALL be bounded by `LLM_TIMEOUT_SECONDS` and at most `LLM_MAX_ATTEMPTS` attempts. A failed attempt is classified as `model_failure` when caused by a model error, a timeout, schema-invalid output, or a citation-subset violation (FR-009.4, FR-011.1), or as `grounding_failure` when caused by a deterministic grounding check (a)-(d) (FR-011.2). Both kinds count toward `LLM_MAX_ATTEMPTS`. After retries are exhausted the system SHALL record no narrative row, SHALL record `investigation.skipped.v1` (FR-009.7) with `inputs.reason` set to the reason of the LAST failed attempt (`model_failure` or `grounding_failure`; see FR-011.2), and SHALL commit the offset: no infinite loop and no crash loop. It SHALL NOT fabricate or substitute a narrative.

**Acceptance Criteria:**
- AC-1: A stub forced to raise results in zero `investigation.drafted.v1` rows, one `investigation.skipped.v1` row with reason `model_failure`, and a committed offset.
- AC-2: A hanging call is aborted at the timeout.
- AC-3: Retries stop after `LLM_MAX_ATTEMPTS`; the failure is recorded as `model_failure` and the consumer moves on without restarting.
- AC-4: A draft citing ids outside the evidence is retried up to the maximum, then recorded as `model_failure` with no `investigation.drafted.v1` row.
- AC-5: Given attempts that fail for different reasons (e.g. attempt 1 grounding check failure, final attempt model error), the skipped row records the reason of the last failed attempt (here `model_failure`); and the reverse order records `grounding_failure`.

### FR-010.5: Local mode (self-hosted model)
`LLM_MODE=local` SHALL send the prompt to a model server that runs as a service inside the Compose deployment, at `LOCAL_LLM_URL`. The investigator and the model server SHALL be reachable from each other only over the internal network (NFR-008.1). Local mode needs no API key. The same prompt, strict output validation, grounding checks (FR-011), retry bounds and skip behavior (FR-010.4) apply as in anthropic mode. `audit.model_version` SHALL record `LLM_MODEL`.

**Acceptance Criteria:**
- AC-1: `LLM_MODE=local` with `LOCAL_LLM_URL` unset exits non-zero at startup.
- AC-2: `LLM_MODE=local` with `LLM_MODEL` unset exits non-zero at startup.
- AC-3: In local mode, a drafted row records `model_version` equal to `LLM_MODEL` and the same `prompt_version` as other modes.
- AC-4: In local mode, an unreachable model server results in `investigation.skipped.v1` with reason `model_failure` after `LLM_MAX_ATTEMPTS`, and a committed offset (FR-010.4).
- AC-5: In local mode, the investigator cannot reach any host outside the deployment (NFR-008 AC-6). Network isolation is the control that keeps `LOCAL_LLM_URL` inside the deployment; the URL host is not otherwise validated.
- AC-6: The model server starts and serves a completion while attached only to the internal network, so its weights are not downloaded at runtime (NFR-008.1).

### FR-010.6: Synthetic-data gate for the external provider
`LLM_MODE=anthropic` sends evidence to a third party, so it SHALL start only when `DATA_CLASSIFICATION=synthetic`. With `DATA_CLASSIFICATION` unset (treated as `customer`) or any other value, startup SHALL fail fast with a clear error, before the API key is read and before any network connection is opened. An unknown `DATA_CLASSIFICATION` value SHALL also fail startup in every mode. In anthropic mode, every drafted and skipped row SHALL record `inputs.data_classification = "synthetic"`. The evaluation script (FR-011.5) SHALL apply the same gate.

**Acceptance Criteria:**
- AC-1: `LLM_MODE=anthropic` with `DATA_CLASSIFICATION` unset exits non-zero, and the key file is never opened (pass a path that would raise).
- AC-2: `LLM_MODE=anthropic` with `DATA_CLASSIFICATION=customer` exits non-zero.
- AC-3: `LLM_MODE=anthropic` with `DATA_CLASSIFICATION=synthetic` and a key starts, and its audit rows carry `inputs.data_classification = "synthetic"`.
- AC-4: `DATA_CLASSIFICATION=bogus` exits non-zero in any mode.
- AC-5: `eval_investigator.py` exits non-zero unless `DATA_CLASSIFICATION=synthetic`.
- AC-6: In stub mode and local mode, `DATA_CLASSIFICATION` unset is accepted (default `customer`).

## Traceability
| Sub-req | Test file (test names) | Source reference |
|---------|-----------|-----------------|
| FR-010.1 | tests/test_investigator.py (test_unset_env_is_stub_customer, test_bogus_mode_exits, test_local_mode_accepted_without_key_read) | investigator.py `load_model_config` |
| FR-010.2 | tests/test_llm.py (test_stub_is_deterministic, test_stub_and_local_never_import_anthropic); tests/conftest.py guard; CI runs without a key | llm.py `StubLLM` |
| FR-010.3 | tests/test_investigator.py (test_anthropic_key_file_wins_over_env, test_anthropic_env_fallback_when_file_absent, test_anthropic_empty_key_file_falls_back_to_env, test_anthropic_synthetic_without_key_exits, test_missing_or_empty_password_exits, test_db_host_default_and_override, test_stack_drafted_row_stub, test_stack_anthropic_synthetic_rows_and_no_key_leak) | investigator.py `load_config` |
| FR-010.4 | tests/test_llm.py (test_retry_exhausts_to_model_failure, test_local_hanging_call_aborted_at_timeout, test_retry_last_reason_follows_last_attempt); tests/test_investigator.py (test_stack_forced_raise_skip_and_redelivery) | llm.py `complete_with_retry` |
| FR-010.5 | AC-1..AC-4: tests/test_investigator.py (test_local_without_url_exits, test_local_without_model_exits, test_stack_local_mode_drafted, test_stack_main_local_unreachable_commits_after_row); tests/test_llm.py (test_local_*). AC-5: tests/egress_check.py + tests/compose_check.py in CI every push. AC-6: opt-in `local-model` job ONLY (not run on push, unverified until dispatched) | llm.py `LocalLLM`, llm.Dockerfile, compose.yaml `llm` |
| FR-010.6 | tests/test_investigator.py (test_anthropic_without_classification_exits_before_any_read, test_anthropic_customer_exits, test_bogus_classification_exits_in_every_mode, test_stub_and_local_accept_synthetic_too, test_main_refuses_anthropic_without_synthetic_before_any_io); tests/test_eval_scenarios.py (test_eval_refuses_unless_anthropic_and_synthetic) | investigator.py `load_model_config`, eval_investigator.py, compose.anthropic.yaml |
