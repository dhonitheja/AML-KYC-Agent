---
id: "FR-008"
title: "Read API"
type: "functional"
priority: "P1"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["api.py", "compose.yaml"]
test_files: []
depends_on: ["FR-004"]
implements: []
---

# FR-008: Read API

## Description
FastAPI service on `127.0.0.1:8000` exposing stored decisions from `audit`. (api.py:7-24; compose.yaml:59)

## Requirements

### FR-008.1: GET /alerts
SHALL return the `inputs` of the 100 most recent `alerted.v1` rows ordered by `event_id` DESC. (api.py:20-24)

**Acceptance Criteria:**
- AC-1: After the seed scenario the list contains an item with `case_id` `AML-1042` (CI check).
- AC-2: With >100 alerts, exactly 100 newest are returned.

### FR-008.2: GET /scores/{transaction_id}
SHALL return the `scored.v1` inputs for the UUID, or HTTP 404 "No recorded score" if none. A non-UUID id SHALL yield 422. (api.py:10-17)

**Acceptance Criteria:**
- AC-1: Known id returns score, alert, rules.
- AC-2: Unknown UUID returns 404.

### FR-008.3: Read-only and local binding
These endpoints SHALL only SELECT and the port SHALL bind to 127.0.0.1 only. (api.py; compose.yaml:59)

**Acceptance Criteria:**
- AC-1: The published port mapping is `127.0.0.1:8000:8000`.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-008.1 | .github/workflows/ci.yml:13 | api.py:20-24 |
| FR-008.2 | none (gap) | api.py:10-17 |
| FR-008.3 | none | compose.yaml:59 |
