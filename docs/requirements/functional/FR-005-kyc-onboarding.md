---
id: "FR-005"
title: "KYC onboarding review"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["api.py", "kyc.py", "sql/003-kyc.sql"]
test_files: ["tests/test_kyc.py"]
depends_on: ["FR-006"]
implements: []
---

# FR-005: KYC onboarding review

## Description
`POST /onboarding` reviews a person or business application: compares applicant to documents, screens all names against the sanctions snapshot, and records the outcome. Findings are advisory; nothing clears, blocks or closes cases.

## Requirements

### FR-005.1: Input validation
The `Application` model SHALL require `application_id` (UUID), `kind` in {person, business}, `applicant`, 1-12 `documents`, 0-25 `owners` (recursive, 0-25 children). `Identity` requires name (screenable after normalize), id_number, address (1-256 chars, stripped), optional date_of_birth. A person SHALL have a birth date and no owners. Invalid input SHALL yield HTTP 422. (kyc.py:9-42)

No test covers this sub-requirement: none (gap).

**Acceptance Criteria:**
- AC-1: A person without DOB, or with owners, is rejected.
- AC-2: A name with no letters/digits is rejected.
- AC-3: 13 documents is rejected.

### FR-005.2: Field mismatch detection
`review()` SHALL compare each document to the applicant on name (normalized), address (casefold token list), id_number and date_of_birth and emit `{document, field, reason}` per difference. A business without owners SHALL emit an `owners` gap. (kyc.py:51-63)

**Acceptance Criteria:**
- AC-1: A document with a reordered/cased name does not mismatch.
- AC-2: A differing id_number yields one mismatch with the 1-based document index.
- AC-3: Business with empty owners yields "Beneficial ownership details missing".

### FR-005.3: Screening of all subjects
It SHALL screen the applicant, every document whose raw (un-normalized) name or date of birth differs from the applicant's (kyc.py:69; mismatch detection in FR-005.2 compares normalized names, kyc.py:57, so a reordered/cased name is not a mismatch yet is still screened as a separate subject), and every owner at any nesting depth, recording a `path` (e.g. `owners[0].owners[1]`). `requires_review` SHALL be true iff there are mismatches or any screening hit. (kyc.py:64-78)

**Acceptance Criteria:**
- AC-1: A sanctioned grand-owner produces a subject with path `owners[i].owners[j]` and hits.
- AC-2: A document alias that differs is screened separately (test_person_conflicting_dob_and_document_alias).

### FR-005.4: Idempotency by application_id
The first submission SHALL persist to `kyc_applications` and audit `kyc.reviewed.v1` (without screening detail) plus one `onboarding.screened.v1` per subject, actor `kyc-screen-v1`. Resubmission with an identical payload SHALL return the stored result and write no new audit rows. (api.py:35-49)

**Acceptance Criteria:**
- AC-1: Second identical POST returns the same body; audit row count unchanged (test_onboard_nested_owners_documents_audit_and_replay).

### FR-005.5: Conflict on changed payload
Same `application_id` with a different payload SHALL return HTTP 409 and store nothing. (api.py:43-44)

**Acceptance Criteria:**
- AC-1: Altered payload returns 409.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-005.1 | none (gap) | kyc.py:9-42 |
| FR-005.2 | tests/test_kyc.py | kyc.py:51-63 |
| FR-005.3 | tests/test_kyc.py | kyc.py:64-78 |
| FR-005.4 | tests/test_kyc.py::test_onboard_nested_owners_documents_audit_and_replay | api.py:35-49; sql/003-kyc.sql:2-5 |
| FR-005.5 | tests/test_kyc.py | api.py:43-44 |
