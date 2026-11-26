---
id: "DI-003"
title: "Quix Streams (stream processing)"
type: "dependency-interface"
status: "superseded"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
source_files: ["scoring.py"]
package: "quixstreams"
version_constraint: "==3.15.0"
satisfies_fr: ["FR-002", "FR-003", "FR-004"]
satisfies_nfr: ["NFR-001", "NFR-002"]
constrained_by_adrs: ["ADR-002", "ADR-005", "ADR-006"]
---

# DI-003: quixstreams

**Superseded in Phase 6 (ADR-032).** `quixstreams` was removed from requirements.txt; the scorer is a confluent_kafka consumer with manual commits (DI-001, CS-002 v1.1). The rest of this page describes the Phase 2-5 design and is kept for history.

## Purpose
Dataframe-style consume/transform/produce loop for the scorer (scoring.py:25-54).

## Classes/Methods/Functions Used
`quixstreams.Application(broker_address, consumer_group="aml-scorer-v1", auto_offset_reset="earliest", producer_extra_config={"linger.ms":1})` (scoring.py:26-27); `app.topic(name, value_deserializer="json" | value_serializer="json")`; `app.dataframe(topic).apply(score)`; `.filter(...)`; `.to_topic(...)`; `app.run()` (scoring.py:52-54).

## Data Exchanged
In: transaction JSON dicts. Out: `scored.v1` inputs to `alerts` for alert records only.

## Failure Modes and Timeouts
- An exception in `score()` stops the app; compose restarts it and Quix resumes from the committed offset.
- Quix checkpoints and publishes after the callback returns (after DB commit): a crash between them can republish an alert, so consumers must dedupe (CS-008 does).
- `linger.ms=1` trades throughput for the 500 ms alert-latency budget (NFR-001).

## Security Notes
Transport is PLAINTEXT in the demo; same TLS/SASL requirements as DI-001 in production. No secrets handled here.

## Why This Dependency
Provides the checkpointed consume-process-produce plumbing. Replacing it requires a hand-written consumer/producer loop (as in pipeline.py) with equivalent commit ordering and a transactional/atomic publish strategy; exact pin because the 3.x API moves between minors.
