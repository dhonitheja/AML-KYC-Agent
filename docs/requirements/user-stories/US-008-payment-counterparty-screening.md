---
id: "US-008"
title: "Screen outbound counterparties once per snapshot"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "AML compliance analyst"
implements_fr: ["FR-007"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_kyc.py"]
epic: "kyc"
---

# US-008: Screen outbound counterparties once per snapshot

## Story
As an **AML compliance analyst**, I want **each outbound counterparty screened once per (account, normalized name, snapshot)**, so that **payments are screened without alert noise or duplicate audit rows**.

## Acceptance Criteria
- [ ] AC-1: Given a payment stream with repeated counterparties, when it is processed, then each new counterparty yields exactly one payment.screened.v1 row.
- [ ] AC-2: Given a changed snapshot hash, when the same counterparty pays again, then it is screened once more.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_kyc.py::test_payment_stream_screens_each_new_counterparty_once | each new counterparty yields exactly one payment.screened.v1 row |
| AC-2 | none yet (planned) | it is screened once more |
