---
id: "FR-006"
title: "Sanctions name screening with versioned snapshots"
type: "functional"
priority: "P0"
status: "implemented"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["watchlist.py", "compose.yaml"]
test_files: ["tests/test_kyc.py"]
depends_on: []
implements: []
---

# FR-006: Sanctions name screening with versioned snapshots

## Description
`watchlist.py` parses OFAC legacy SDN XML into an immutable snapshot and fuzzy-screens names against it. Default source is the fictional fixture `watchlists/sample.xml`.

## Requirements

### FR-006.1: Safe SDN parsing and validation
`parse()` SHALL use `defusedxml`, strip namespaces, require root `sdnList`, require each entry to have a uid and screenable name, include `akaList` aliases, and reject empty snapshots or a `Record_Count` that mismatches entry count. (watchlist.py:68-91)

**Acceptance Criteria:**
- AC-1: Non-SDN root raises ValueError("Expected SDN XML").
- AC-2: Entry without uid raises "Incomplete SDN entry".
- AC-3: XML with entity-expansion payload is rejected.

### FR-006.2: Name normalization
`normalize()` SHALL casefold, strip accents, drop punctuation and sort tokens, so token order and diacritics do not affect matching. (watchlist.py:20-23)

**Acceptance Criteria:**
- AC-1: "Meridian, Cobalt" and "cobalt meridian" normalize equally.

### FR-006.3: Fuzzy matching threshold
`screen()` SHALL use RapidFuzz `fuzz.ratio` with cutoff 88 over primary names and aliases, keep the best score per entry uid, round to 2 decimals, and sort hits by (-score, entry_id). An unscreenable name SHALL raise ValueError. Result includes `name`, `snapshot`, `threshold: 88`, `hits`. (watchlist.py:42-65)

**Acceptance Criteria:**
- AC-1: Seeded names, variants and aliases hit (test_seeded_names_variants_and_aliases).
- AC-2: "Juniper Orchard Services" returns no hits (test_clean_name).

### FR-006.4: DOB disposition
Each hit SHALL have `disposition`: `corroborated_match` if the supplied DOB equals a listed full date; `conflicting_dob` if a DOB is supplied, all listed dates are full, and none match; otherwise `possible_match`. An entry with no listed dates SHALL yield `possible_match` (watchlist.py:59). (watchlist.py:53-61)

**Acceptance Criteria:**
- AC-1: Matching DOB gives corroborated_match; differing DOB gives conflicting_dob (test_person_conflicting_dob_and_document_alias).
- AC-2: No DOB supplied gives possible_match.
- AC-3: An entry with no listed dates gives possible_match even when a DOB is supplied.

### FR-006.5: Versioned snapshot
Snapshot `version` SHALL be the SHA-256 of the raw file bytes. `active()` SHALL load `SDN_FILE` (default `watchlists/sample.xml`) with an `lru_cache` keyed by path, mtime and size. (watchlist.py:91-102; compose.yaml:46,57)

**Acceptance Criteria:**
- AC-1: Same bytes give same version; any byte change gives a different version.
- AC-2: Changing the file invalidates the cache key (mtime/size).
- AC-3: With `SDN_FILE` unset, `active()` loads `watchlists/sample.xml` (watchlist.py DEFAULT); with `SDN_FILE=<path>` it loads that file.

### FR-006.6: OFAC loader
`python watchlist.py` SHALL download the SDN XML (90 s timeout, 128 MiB cap), validate via `parse`, and atomically replace `watchlists/sdn.xml` (mode 0644), printing entry count and SHA-256. (watchlist.py:105-116)

**Acceptance Criteria:**
- AC-1: Oversized response raises ValueError and leaves the destination unchanged.
- AC-2: Invalid XML leaves the destination unchanged.

## Traceability
| Sub-req | Test file | Source reference |
|---------|-----------|-----------------|
| FR-006.1 | none directly (gap) | watchlist.py:68-91 |
| FR-006.2 | tests/test_kyc.py | watchlist.py:20-23 |
| FR-006.3 | tests/test_kyc.py | watchlist.py:42-65 |
| FR-006.4 | tests/test_kyc.py | watchlist.py:53-61 |
| FR-006.5 | none directly | watchlist.py:94-102 |
| FR-006.6 | none (network; manual) | watchlist.py:105-116 |
