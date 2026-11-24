---
id: "ADR-030"
title: "Synthetic-data gate for the external model provider"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-23"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-008", "NFR-006", "NFR-005"]
focus_track: "security"
evidence: "documented"
---

# ADR-030: Synthetic-data gate for the external model provider

## Status
Accepted by the user at the Design sign-off (2026-11-24, NFR-008 delta).

## Context
Anthropic mode sends evidence to a third party. NFR-008.3(a) allows that only for synthetic data; FR-010.6 requires a startup gate; FR-011.5 AC-3 extends the gate to the evaluation script. Docker cannot restrict egress by hostname. The compose file currently defaults `LLM_MODEL` to `claude-opus-5-5` (ADR-022), which would make `LLM_MODEL` always set and defeat FR-010.5 AC-2 (required, no default in local mode). Sources: FR-010.6, CS-008 v1.1, ARCH-001 B12, RR-24.

## Decision
We will gate the external provider on `DATA_CLASSIFICATION` (`customer` default when unset, or `synthetic`; any other value exits in every mode):
- Validation order in `load_config`: valid `LLM_MODE` and `DATA_CLASSIFICATION`; then the gate (anthropic with classification not `synthetic` exits); then mode-specific reads. The gate runs before the API key is read, before the DB password secret is read, and before any socket, DB or Kafka connection.
- `inputs.data_classification` is stamped on every drafted and skipped row in ALL modes, from validated config only (CS-008 choice: one row shape, shows the classification each row was produced under). The narrower alternative, stamping only in anthropic mode where the gate guarantees `synthetic`, is not taken; it would save one field in stub/local rows but give two row shapes.
- Anthropic egress exists only through `compose.anthropic.yaml`, an override that adds `investigator` to the `egress` network and mounts the key secret. Base `compose.yaml` therefore always satisfies NFR-008 AC-1/AC-7, and a mis-set `LLM_MODE=anthropic` also fails closed at the network layer.
- We will not build a host-restricting egress proxy. Residual RR-24 (the investigator, with DB access and evidence, can reach any internet host in anthropic mode) is accepted, mitigated by the gate and the opt-in file; an allow-listing proxy is the upgrade path.
- No Compose default for the model: `LLM_MODEL: ${LLM_MODEL:-}` (empty = unset). Mode-aware defaults live in `load_config` only (anthropic: `claude-opus-5-5`; local: required; stub: ignored). Empty strings count as unset for `LLM_MODEL`, `LOCAL_LLM_URL` and `DATA_CLASSIFICATION`.
- `eval_investigator.py` reuses the same `load_config` gate (anthropic and synthetic required) so the two cannot drift.

## Consequences
Positive: customer data cannot be sent to a hosted provider by accident (two independent controls, config gate plus network route); the gate is a pure unit test (NFR-008 AC-3).

Negative: anthropic mode needs two deliberate steps (env var and override file); RR-24 stays open; stub/local rows carry an extra field; the compose default for `LLM_MODEL` is removed, so existing habits change; the gate is self-attested (an operator can label real data `synthetic`), so it prevents mistakes, not malice.

Rejected alternative: a host-restricting egress proxy allow-listing `api.anthropic.com` (new service, TLS or CONNECT filtering, new trust component). Cost accepted: RR-24.

Relations: extends ADR-022 (does not supersede; SDK, pin, retry and recorded versions unchanged, only the compose `LLM_MODEL` default is removed). Related: ADR-021 (key read after the gate), ADR-028 (egress network), ADR-029 (local mode).
