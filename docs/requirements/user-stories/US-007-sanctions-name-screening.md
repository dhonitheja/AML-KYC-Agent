---
id: "US-007"
title: "Screen names against versioned sanctions snapshots"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "KYC onboarding officer"
implements_fr: ["FR-006"]
implements_nfr: ["NFR-004"]
test_files: ["tests/test_kyc.py"]
epic: "kyc"
---

# US-007: Screen names against versioned sanctions snapshots

## Story
As a **KYC onboarding officer**, I want **fuzzy name matching against the OFAC snapshot with the snapshot SHA-256 recorded**, so that **hits are reproducible against the exact list used**.

## Acceptance Criteria
- [ ] AC-1: Given seeded names, variants and aliases (e.g. Cobalt Meridian Exports), when they are screened at threshold 88, then a hit is returned.
- [ ] AC-2: Given a clean name (Juniper Orchard Services), when it is screened, then no hit is returned.
- [ ] AC-3: Given any screening result, when it is audited, then the snapshot hash is recorded.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | tests/test_kyc.py::test_seeded_names_variants_and_aliases | a hit is returned |
| AC-2 | tests/test_kyc.py::test_clean_name | no hit is returned |
| AC-3 | none yet (gap) | the snapshot hash is recorded |
