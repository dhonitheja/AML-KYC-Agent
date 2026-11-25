---
id: "ADR-033"
title: "Account-keyed 16-partition transactions topic with scorer replicas"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-24"
author: "adr-author-agent"
supersedes: ["ADR-002"]
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-009"]
evidence: "benchmark"
---

# ADR-033: Account-keyed 16-partition transactions topic with scorer replicas

## Status
Accepted by the user at the Phase 6 design check (2026-11-24). Supersedes ADR-002 for `transactions`; `alerts` stays single-partition.

## Context
ADR-002 ran both topics with one partition, which caps the scorer at one process. Batching alone (ADR-032) reached about 245/s per scorer. NFR-009 needs 1,000/s.

## Decision
We will create `transactions` with 16 partitions and run `SCORER_REPLICAS` (default 8) scorer processes in one consumer group. Messages stay keyed by account, so each account's events land on one partition and are scored serially by one scorer. That keeps the velocity windows and the 48 h history correct. `alerts` stays at one partition, because ADR-017 and ADR-023 rely on it and the investigator asserts it at startup. The `topic` service only creates missing topics. It never repartitions an existing one, because adding partitions remaps keys and could reorder an account's in-flight events. To upgrade an existing volume: stop every producer (ingest CLI runs, generators), let the scorer and ingest groups drain `transactions` to zero lag, run `docker compose exec kafka rpk topic add-partitions transactions --num 15 -X brokers=kafka:9092` (the broker port is not published to the host), then restart producers. An event produced between the drain and the change could stay on its old partition while a later event for the same account lands on a new one and is scored first. Or start on fresh volumes.

## Consequences
Positive: scoring scales horizontally up to 16 processes. Measured capacity is at least 1,585/s with 8 replicas, while the latency gate improved (p95 59 ms). Negative: a scorer joining or leaving triggers a group rebalance, which briefly stalls scoring (latency p95 rose to 725 ms on one run taken during the rebalance right after startup). Postgres becomes the shared bottleneck, and throughput falls once the database outgrows its cache (NFR-009 known limits). Total ordering across accounts is gone. No rule depends on it.
