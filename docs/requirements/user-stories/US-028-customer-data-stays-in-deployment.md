---
id: "US-028"
title: "Customer data never leaves the deployment"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-23"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "compliance officer"
implements_fr: ["FR-009", "FR-010"]
implements_nfr: ["NFR-008"]
test_files: ["tests/compose_check.py", "tests/egress_check.py", "tests/test_investigator.py"]
epic: "data-protection"
---

# US-028: Customer data never leaves the deployment

## Story
As a **compliance officer**, I want **customer data to stay inside our own deployment, with no service or agent able to send it to a third party or another agent**, so that **a bug, a misconfiguration or a compromised agent cannot cause a data breach**.

Accepted exception (NFR-008.3(e), ADR-028, RR-23): `api` keeps a technical outbound route through the `ingress` network. Its code makes no outbound calls, but a compromise of `api` itself is not stopped by a network control.

## Acceptance Criteria
- [x] AC-1: Given the stack runs in the default stub mode, when the investigator or scorer container tries to open a connection to an external host, then the connection fails (NFR-008 AC-1).
- [x] AC-2: Given the Compose configuration, when it is rendered, then postgres, redis and kafka publish no host ports and the API is bound only to 127.0.0.1 (NFR-008 AC-2).
- [x] AC-3: Given anthropic mode is selected without DATA_CLASSIFICATION=synthetic, when the investigator starts, then it refuses to start before reading the key or opening a connection (FR-010.6 AC-1, AC-2).
- [x] AC-4: Given an alert is drafted or skipped, when the investigator logs it, then the log contains no counterparty name and no amount (NFR-008 AC-4).
- [x] AC-5: Given the Compose configuration, when it is rendered, then every data-holding service is on the internal network only, the API also joins only the loopback ingress network, and the OFAC fetch service cannot reach the database (NFR-008 AC-7, AC-8).

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/egress_check.py (CI) from investigator and scorer (CI step, not pytest) | external connection fails from investigator and scorer |
| AC-2 | tests/compose_check.py (CI) | no host ports except loopback API |
| AC-3 | tests/test_investigator.py (test_anthropic_without_classification_exits_before_any_read, test_main_refuses_anthropic_without_synthetic_before_any_io) | anthropic mode refused without synthetic declaration |
| AC-4 | tests/test_investigator.py (test_stack_logs_carry_no_evidence) | logs carry no evidence fields |
| AC-5 | tests/compose_check.py (CI); tests/egress_check.py (CI) --deny postgres:5432 in watchlist-fetch (CI) | network attachments; fetch service isolated from DB |
