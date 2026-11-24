---
id: "DI-001"
title: "confluent-kafka (Kafka client; Redpanda broker)"
type: "dependency-interface"
status: "approved"
version: "1.0"
created: "2026-11-22"
author: "component-spec-author-agent"
package: "confluent-kafka"
version_constraint: "<3"
satisfies_fr: ["FR-001", "FR-004", "FR-009"]
satisfies_nfr: ["NFR-001", "NFR-002", "NFR-006"]
constrained_by_adrs: ["ADR-001", "ADR-002", "ADR-005", "ADR-006", "ADR-017"]
---

# DI-001: confluent-kafka

## Purpose
Producer and consumer client (librdkafka) for the Redpanda broker `kafka:9092` (compose.yaml:3-4). Topics `transactions` and `alerts`, 1 partition each (compose.yaml:14).

## Classes/Methods/Functions Used
- `Producer({"bootstrap.servers", "enable.idempotence": True})`, `list_topics`, `produce(key, value, on_delivery)`, `poll`, `flush` (pipeline.py:29-47); `Producer(... linger.ms=0)` (latency.py:37).
- `Consumer({"bootstrap.servers","group.id","auto.offset.reset":"earliest","enable.auto.commit":False})`, `subscribe`, `consume(100, 0.25)`, `commit(asynchronous=False)`, `close` (pipeline.py:66-83).
- `Consumer.get_watermark_offsets`, `assign`, `TopicPartition`, `poll` (latency.py:38-44, 23).
- New (CS-008): `Consumer` group `aml-investigator-v1`, `max.poll.interval.ms >= (LLM_TIMEOUT_SECONDS*LLM_MAX_ATTEMPTS + backoff + 60)*1000`, `list_topics("alerts")` to assert 1 partition, `poll`, `commit(asynchronous=False)`.

## Data Exchanged
JSON strings: transactions (`id, run_id, case_id, account, counterparty, amount_cents, direction, channel, occurred_at`) keyed by account; alerts (scored.v1 inputs, no account field, rules.py:30-31).

## Failure Modes and Timeouts
- Delivery failure: `flush(30)` non-zero or callback error raises `RuntimeError` (pipeline.py:46-47).
- Consumer `msg.error()` raises, service exits, compose restarts (`restart: on-failure`).
- Rebalance/long processing: exceeding `max.poll.interval.ms` evicts the consumer; the investigator sizes it above worst-case LLM time.
- Offsets are committed after DB commit only; crash means redelivery (at-least-once), consumers dedupe.
- If `alerts` ever gets more than 1 partition, ordering and the single-partition assumption in CS-008 break; CS-008 refuses to start.

## Security Notes
Demo broker is PLAINTEXT with no auth inside the compose network and no host port published. Production would require TLS (`security.protocol=SSL`/`SASL_SSL`), SASL credentials from secret files and per-service ACLs (investigator: read `alerts` only, no produce to `transactions`/`alerts`, FR-009.6). Alert payloads contain transaction ids and rule evidence, no raw account (NFR-006).

## Why This Dependency
Direct, low-latency, exactly-controlled offset commits. Replacing it (e.g. kafka-python, aiokafka) requires re-implementing manual commit semantics, idempotent producer and watermark access in pipeline.py, latency.py and CS-008; the pinned `<3` guards against a major API break.
