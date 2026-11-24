---
id: "ADR-001"
title: "Redpanda as the Kafka broker"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-001", "NFR-007"]
evidence: "documented"
---

# ADR-001: Redpanda as the Kafka broker

## Status
Accepted (retroactive record of a decision already embodied in the code).

## Context
The pipeline needs a Kafka-protocol broker that starts quickly and fits a single-machine Docker Compose demo within the CI budget (NFR-007). compose.yaml:3 pins `redpanda:v24.3.10` and starts it in `--mode dev-container --smp 1 --memory 512M` (compose.yaml:4); a one-shot `topic` service (compose.yaml:11-16) creates the topics. R-01 in ARCH-001.

## Decision
We will use Redpanda v24.3.10 as the Kafka-API broker, single node, with clients written against the Kafka protocol (confluent_kafka, Quix Streams) so the broker stays replaceable.

## Consequences
Positive: one small container, no ZooKeeper/KRaft setup, fast health check (compose.yaml:7-10), helps the CI time budget (NFR-007). Negative: dev-container mode is not a production configuration; PLAINTEXT without SASL/ACL (RR-1); single node means no replication. `rpk` is used in compose only, not in application code.
