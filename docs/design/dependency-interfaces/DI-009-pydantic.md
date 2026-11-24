---
id: "DI-009"
title: "pydantic v2 (validation)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "pydantic"
version_constraint: ">=2.7,<3"
satisfies_fr: ["FR-005", "FR-008", "FR-009"]
satisfies_nfr: ["NFR-006"]
constrained_by_adrs: ["ADR-019"]
---

# DI-009: pydantic

## Purpose
Strict input validation at trust boundaries: onboarding payloads today, alert payloads and model output in Phase 4.

## Classes/Methods/Functions Used
Existing: `BaseModel`, `Field`, `StringConstraints`, `field_validator`, `model_validator` (kyc.py:5, 9, 12-42), `model_dump(mode="json")` (api.py:34).
New (CS-008): `AlertIn` and `Draft`, both `model_config = ConfigDict(extra="forbid", strict=True)`; `Draft.model_validate_json(raw)`; `Literal` for the recommendation enum; `Field(max_length=2000)` and `min_length=1` list for `cited_transaction_ids`; the subset-of-evidence check is an explicit post-validation step (needs runtime context).

## Data Exchanged
Alert JSON from Kafka (untrusted input), model JSON text (untrusted output), onboarding bodies.

## Failure Modes and Timeouts
`ValidationError` is converted to a typed outcome (`malformed_alert` or a retryable model validation failure); its message is never logged because it can echo input values.

## Security Notes
`extra="forbid"` blocks smuggled fields; length caps bound audit row size.

## Why This Dependency
Already the validation layer and a FastAPI requirement; replacing it affects the API and every model.
