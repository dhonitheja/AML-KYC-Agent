---
id: "US-011"
title: "Ingestion throughput of at least 50 rows/s"
type: "user-story"
priority: "P1"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
persona: "platform engineer"
implements_fr: ["FR-001"]
implements_nfr: ["NFR-001"]
test_files: []
epic: "performance"
---

# US-011: Ingestion throughput of at least 50 rows/s

## Story
As a **platform engineer**, I want **the benchmark to verify sustained ingestion**, so that **the pipeline keeps up with volume**.

## Acceptance Criteria
- [ ] AC-1: Given a 60 s benchmark, when it finishes, then at least 50 rows/s were persisted with matching audit rows.

## Test Coverage
| Criterion | Test file | Description |
|-----------|-----------|-------------|
| AC-1 | benchmark command (no pytest file) | at least 50 rows/s were persisted with matching audit rows |
