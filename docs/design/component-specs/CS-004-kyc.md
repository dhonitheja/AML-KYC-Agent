---
id: "CS-004"
title: "KYC: onboarding review and payment screening"
type: "component-spec"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["kyc.py"]
satisfies_fr: ["FR-005", "FR-006", "FR-007"]
satisfies_nfr: ["NFR-002", "NFR-004", "NFR-005", "NFR-006"]
constrained_by_adrs: ["ADR-003", "ADR-004", "ADR-009", "ADR-010", "ADR-011", "ADR-015", "ADR-016"]
---

# CS-004: kyc.py

## Description
Pydantic models for onboarding applications, the `review()` comparison/screening function, the shared `audit()` helper and outbound-counterparty `payment_screen()`. Findings are recorded only; nothing is cleared, blocked or closed.

## Public Interface
- `Text` constrained string: strip, 1..256 chars (kyc.py:9).
- `Identity` (kyc.py:12-23): name (must normalize non-empty), date_of_birth, id_number, address.
- `Owner` (kyc.py:26-28): recursive, `owners` max 25. `Application` (kyc.py:31-42): `application_id` UUID, `kind` person|business, `documents` 1..12, `owners` max 25; a person needs a birth date and no owners (kyc.py:38-42).
- `audit(db, action, payload, case_id=None, transaction_id=None)` (kyc.py:45-48): inserts as actor `kyc-screen-v1`.
- `review(app, snapshot) -> dict` (kyc.py:51-78): `{application_id, kind, mismatches, screening, requires_review}`.
- `payment_screen(db, row)` (kyc.py:81-90): debit only.

## Internal Data Structures
`gaps` list `{document?, field, reason}`; `subjects` list `{path, name, snapshot, threshold, hits}`; table `screened_counterparties(account, name_key, snapshot)`.

## Key Algorithms
- Mismatch: each document is compared field-wise to the applicant; name via `normalize`, address via casefolded token lists (kyc.py:53-61); business without owners flagged (kyc.py:62-63).
- Screening subjects: applicant, documents differing by name/DOB, every owner recursively with path labels (kyc.py:64-76).
- Payment: `INSERT INTO screened_counterparties ... ON CONFLICT DO NOTHING RETURNING account`; only on first insert, screen and write `payment.screened.v1` with inputs `{account, name, snapshot, threshold, hits}` (kyc.py:85-90). Once per (account, normalized name, snapshot hash).

## Component Interactions
Uses CS-005 (`active`, `normalize`); called by CS-006 (`/onboarding`) and CS-002. `payment.screened.v1` rows are read by CS-008 via `inputs->>'account'`.

## Invariants
- Screening hits carry the snapshot hash (`snapshot`) for reproducibility.
- No account-to-application link exists (FR-009.8 limitation).
- Writes are append-only.

## Traceability
FR-005, FR-006 (via `review`), FR-007; NFR-002 (once-per-key), NFR-004, NFR-005, NFR-006.
