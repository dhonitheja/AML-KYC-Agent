---
id: "ADR-015"
title: "Synthetic data only"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-006"]
evidence: "documented"
---

# ADR-015: Synthetic data only

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
Producers generate fictional accounts (`DEMO-nnn`), merchants and the fixed AML-1042 scenario (pipeline.py:16-26,121); the default SDN file is a fictional fixture (watchlist.py:1,17); passwords are demo values. NFR-006 requires no real PII or credentials. R-15.

## Decision
We will process synthetic data only, and rely on that fact to accept several security gaps (plaintext transport, raw PII jsonb, no API auth).

## Consequences
Positive: no privacy or regulatory exposure in the demo; permits deferrals RR-1, RR-2, RR-3, RR-6. Negative: every deferral is conditional on this ADR; moving to real data invalidates those acceptances, and sending data to a third-party model (ADR-022) additionally needs a data-processing agreement.

## Amendment (accepted 2026-11-24, see ADR-028 to ADR-030)
NFR-006 v1.2 narrows "synthetic only" to the repo, CI and demo; NFR-008 and ADR-028..030 govern any deployment holding customer data. Residual risks RR-1, RR-2, RR-3 and RR-6, which rely on synthetic data, must be re-assessed before any real-data deployment. The decision text above is unchanged.
