---
id: "US-005"
title: "Review onboarding applications for name and owner risk"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "KYC onboarding officer"
implements_fr: ["FR-005"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_kyc.py"]
epic: "kyc"
---

# US-005: Review onboarding applications for name and owner risk

## Story
As a **KYC onboarding officer**, I want **POST /onboarding to compare applicant and document fields and screen the applicant and all nested owners**, so that **onboarding risks are surfaced before an account is opened**.

## Acceptance Criteria
- [ ] AC-1: Given an application with nested owners and documents, when it is submitted, then each owner, applicant and differing document name is screened and kyc.reviewed.v1 / onboarding.screened.v1 audit rows are written.
- [ ] AC-2: Given a person with conflicting DOB and a document alias, when it is reviewed, then the mismatches and alias hit are reported.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_kyc.py::test_onboard_nested_owners_documents_audit_and_replay | each owner, applicant and differing document name is screened and kyc. |
| AC-2 | tests/test_kyc.py::test_person_conflicting_dob_and_document_alias | the mismatches and alias hit are reported |
