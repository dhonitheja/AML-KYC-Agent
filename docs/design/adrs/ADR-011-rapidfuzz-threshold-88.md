---
id: "ADR-011"
title: "RapidFuzz threshold 88 with token-sorted normalization"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-004"]
evidence: "documented"
---

# ADR-011: RapidFuzz threshold 88 with token-sorted normalization

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Name matching uses `fuzz.ratio` with `score_cutoff=88` over names normalized by NFKD, casefold, accent strip and sorted alphanumeric tokens (watchlist.py:20-23,47); the threshold is echoed in output (watchlist.py:64). R-11.

## Decision
We will screen with RapidFuzz ratio at threshold 88 on token-sorted normalized names, and emit dispositions (`possible_match`, `corroborated_match`, `conflicting_dob`) for analyst review rather than a block/allow decision.

## Consequences
Positive: fast, order-insensitive matching with alias support; deterministic. Negative: 88 is an uncalibrated constant (no false-positive/negative study); sorting tokens loses word-order signal; transliteration beyond NFKD is not handled.
