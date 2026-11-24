---
id: "DI-008"
title: "defusedxml (safe XML parsing)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "defusedxml"
version_constraint: "==0.7.1"
satisfies_fr: ["FR-006"]
satisfies_nfr: ["NFR-006", "NFR-004"]
constrained_by_adrs: ["ADR-010"]
---

# DI-008: defusedxml

## Purpose
Parses the OFAC SDN XML, which may come from the network (`refresh()`), without XXE or entity-expansion attacks.

## Classes/Methods/Functions Used
`defusedxml.ElementTree.fromstring(data)` (watchlist.py:13, 69).

## Data Exchanged
Raw SDN XML bytes in; `Element` tree out; parsed into `Snapshot` (version = SHA-256 of the bytes, watchlist.py:91).

## Failure Modes and Timeouts
Forbidden constructs or malformed XML raise; `parse` also rejects missing `sdnList`, empty lists and Record_Count mismatch, and `refresh()` never replaces the file on failure (watchlist.py:111-115). Download is capped at 128 MiB with a 90 s timeout (watchlist.py:107-110).

## Security Notes
Security-critical: never substitute stdlib `xml.etree` for untrusted input. Exact pin; the 0.7.1 package is unmaintained-stable, monitor in Operate.

## Why This Dependency
Smallest hardened drop-in for ElementTree. Replacing it needs equivalent entity/DTD prohibition (e.g. lxml with `resolve_entities=False, no_network=True`) and re-verified parsing of the SDN format.
