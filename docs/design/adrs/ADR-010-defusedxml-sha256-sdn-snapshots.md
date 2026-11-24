---
id: "ADR-010"
title: "defusedxml parsing with SHA-256 SDN snapshots"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-004", "NFR-006"]
evidence: "documented"
---

# ADR-010: defusedxml parsing with SHA-256 SDN snapshots

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
The OFAC SDN list is external XML. watchlist.py:13 uses `defusedxml.ElementTree`; `refresh()` caps the body at 128 MiB (watchlist.py:107-110), validates via `parse()` including a Record_Count completeness check (watchlist.py:88-90), and writes atomically with `os.replace` (watchlist.py:112-115). `Snapshot.version` is the SHA-256 of the bytes (watchlist.py:91) and is recorded in each screening result (watchlist.py:64). requirements.txt:9 pins defusedxml==0.7.1. R-10.

## Decision
We will parse untrusted XML only with defusedxml, treat the file hash as the snapshot version, and record that version with every screening result.

## Consequences
Positive: XXE and entity-expansion hardening; any hit is reproducible against a named snapshot (NFR-004). Negative: no signature verification beyond TLS (B9 residual); the cache is per process keyed by path/mtime/size (watchlist.py:94-102), so changing the list may need a restart; parse errors are untested (requirements gap FR-006).
