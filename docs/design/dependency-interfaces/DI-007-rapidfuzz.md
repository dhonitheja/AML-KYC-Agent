---
id: "DI-007"
title: "RapidFuzz (fuzzy name matching)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "rapidfuzz"
version_constraint: ">=3.9,<4"
satisfies_fr: ["FR-005", "FR-006", "FR-007"]
satisfies_nfr: ["NFR-001", "NFR-004"]
constrained_by_adrs: ["ADR-011"]
---

# DI-007: rapidfuzz

## Purpose
Similarity scoring of normalized names against SDN aliases.

## Classes/Methods/Functions Used
`rapidfuzz.fuzz.ratio` and `rapidfuzz.process.extract_iter(key, choices, scorer=fuzz.ratio, score_cutoff=88)` (watchlist.py:14, 47). Imported at watchlist.py:14.

## Data Exchanged
In: token-sorted normalized strings. Out: `(choice, score, index)`; score rounded to 2 decimals and stored in screening hits.

## Failure Modes and Timeouts
CPU-bound linear scan over all aliases per screen (full SDN is large; payment screening is once per (account, name, snapshot) to bound cost, kyc.py:85-90). No timeout.

## Security Notes
Pure computation; no network or file access. Threshold 88 is recorded in output so results are reproducible.

## Why This Dependency
Fast C++ scorers. Replacing it (difflib, jellyfish) changes scores near the threshold and invalidates comparability of stored `payment.screened.v1`/`onboarding.screened.v1` hits; a snapshot-version-style scorer version would be needed.
