---
id: "US-006"
title: "Idempotent onboarding by application_id"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "KYC onboarding officer"
implements_fr: ["FR-005"]
implements_nfr: ["NFR-002"]
test_files: ["tests/test_kyc.py"]
epic: "kyc"
---

# US-006: Idempotent onboarding by application_id

## Story
As a **KYC onboarding officer**, I want **resubmitting an application to be safe and conflicting resubmissions rejected**, so that **retries never create duplicate reviews**.

## Acceptance Criteria
- [ ] AC-1: Given an application_id already processed with identical payload, when it is posted again, then the original result is returned and no new audit rows are added.
- [ ] AC-2: Given the same application_id with a different payload, when it is posted, then the API returns 409.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_kyc.py::test_onboard_nested_owners_documents_audit_and_replay | the original result is returned and no new audit rows are added |
| AC-2 | tests/test_kyc.py | the API returns 409 |
