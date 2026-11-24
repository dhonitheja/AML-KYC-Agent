---
id: "US-010"
title: "Alert latency under 500 ms"
type: "user-story"
priority: "P0"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-002"]
implements_nfr: ["NFR-001"]
test_files: ["latency.py"]
epic: "performance"
---

# US-010: Alert latency under 500 ms

## Story
As a **platform engineer**, I want **the p95 end-to-end alert latency measured over 40 scenarios**, so that **real-time monitoring is met**.

## Acceptance Criteria
- [ ] AC-1: Given 40 latency scenarios, when latency.py runs, then p95 < 500 ms.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | latency.py | p95 < 500 ms |
