---
id: "CS-005"
title: "Watchlist: SDN parsing and fuzzy screening"
type: "component-spec"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["watchlist.py"]
satisfies_fr: ["FR-005", "FR-006", "FR-007"]
satisfies_nfr: ["NFR-004", "NFR-006", "NFR-008"]
constrained_by_adrs: ["ADR-010", "ADR-011", "ADR-013", "ADR-015", "ADR-028"]
---

# CS-005: watchlist.py

## Description
Loads OFAC legacy SDN XML safely, normalizes names, screens by fuzzy matching and versions each snapshot by SHA-256.

## Public Interface
- `normalize(name)` (watchlist.py:20-23): NFKD, casefold, strip accents, tokens `[^\W_]+` sorted and joined.
- `Snapshot.screen(name, dob=None)` (watchlist.py:42-65): `rapidfuzz.process.extract_iter(..., fuzz.ratio, score_cutoff=88)`; best score per SDN uid; disposition `possible_match`, `corroborated_match` (DOB equals a listed date) or `conflicting_dob` (all listed dates are full and differ). Returns `{name, snapshot, threshold:88, hits}` sorted by (-score, entry_id). Empty normalized name raises `ValueError`.
- `parse(data)` (watchlist.py:68-91): defusedxml parse, namespace strip, requires `sdnList` root, non-empty entries, Record_Count match; version = SHA-256 of the bytes.
- `active()` (watchlist.py:99-102): path from `SDN_FILE` (default `watchlists/sample.xml`); `lru_cache(maxsize=2)` keyed on (path, mtime_ns, size) (watchlist.py:94-96).
- `refresh()` (watchlist.py:105-116): HTTPS download (90 s timeout, 128 MiB cap), parse-validate, atomic `os.replace`.

## Internal Data Structures
`Snapshot(version, entries, choices, aliases)` dataclass (watchlist.py:35-40): `choices` are normalized aliases parallel to `aliases` `(entry_index, alias)`.

## Key Algorithms
Token-sorted normalization then `fuzz.ratio >= 88`; DOB comparison refines the disposition only, never suppresses a hit.

## Component Interactions
Used by CS-004. DI-007 (rapidfuzz), DI-008 (defusedxml). Network only in `refresh()` (CLI, not a service).

## Invariants
Incomplete or oversized snapshots are rejected before replacing the file; matches are recorded only, decisions belong to analysts (NFR-005); snapshot change requires service restart or file change (cache key).

## Traceability
FR-006 (sanctions screening, snapshot versioning), FR-007, FR-005; NFR-004, NFR-006 (fictional fixture by default).

## Deployment note (NFR-008, ARCH-001 B17, ADR-028)
`refresh()` (the OFAC download) runs only in the one-shot `watchlist-fetch` service: Compose profile `fetch` (never started by default), attached to the `egress` network only and not to `internal`, no secrets, write mount `./watchlists` only, no database connection, HTTP GET of public data only. `api` and `scorer` (internal network, no egress) only read `./watchlists` and mount it read-only. Screening code paths (`active()`, `screen()`) make no network calls.

## Change notes
- v1.1 (2026-11-23, NFR-008): NFR-008 added to `satisfies_nfr`; deployment note for the isolated fetch service. No code-behavior change.
