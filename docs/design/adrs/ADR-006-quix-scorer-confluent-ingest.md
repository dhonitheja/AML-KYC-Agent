---
id: "ADR-006"
title: "Quix Streams for the scorer, confluent_kafka for ingest"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-002"]
evidence: "documented"
---

# ADR-006: Quix Streams for the scorer, confluent_kafka for ingest

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
The scorer is a stream transform `dataframe.apply(score).filter(alert).to_topic("alerts")` (scoring.py:52-54). Ingest is a plain consume-write-commit loop with explicit batching and commits (pipeline.py:62-83). requirements.txt:3 pins `quixstreams==3.15.0`; `confluent-kafka<3` (requirements.txt:1). R-06.

## Decision
We will use Quix Streams for the scorer (declarative produce path, less plumbing) and a hand-written confluent_kafka consumer for ingest (explicit batch and commit control).

## Consequences
Positive: each component uses the tool that fits it. Negative: two Kafka client styles to maintain; Quix hides commit mechanics (ADR-005 partial evidence); the exact-pinned Quix is a supply-chain item to monitor. ADR-017 rejects Quix for the investigator for control-flow reasons.
