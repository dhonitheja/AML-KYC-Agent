---
id: "ADR-026"
title: "Non-root container user for all services"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-003", "NFR-006"]
focus_track: "security"
evidence: "inferred"
---

# ADR-026: Non-root container user for all services

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
Dockerfile:1-8 has no `USER`, so every service (ingest, scorer, api, and the new investigator) runs as root in the container (RR-13, AC-6). Design decision D10; B8.

## Decision
We will create a system user in the Dockerfile (`useradd --system --uid 10001 app`) and set `USER app` for all services built from it.

## Alternatives rejected
- Root only for the new investigator service: leaves the other three services, including the public API, unnecessarily privileged.

## Consequences
Positive: reduces container-escape and file-write impact. Negative (cost accepted): file permission considerations: `/app` and `watchlists/` must be readable by uid 10001, any runtime write (e.g. `watchlists/sdn.xml` via `refresh()`, watchlist.py:106-115, a manual command) needs a writable path, and mounted volumes need matching ownership.
