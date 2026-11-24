---
id: "ADR-023"
title: "Draft/skip mutual exclusion via combined partial unique index"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-22"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-002", "NFR-004"]
evidence: "inferred"
---

# ADR-023: Draft/skip mutual exclusion via combined partial unique index

## Status
Accepted (user sign-off at the Design checkpoint, 2026-11-23).

## Context
Each alert must end with exactly one advisory outcome: a drafted narrative or a skipped record, never both and never two drafts (FR-009.5). A pre-check plus advisory lock (ADR-017) is not sufficient beyond one consumer because the lock is released before the model call and is transaction-scoped. Existing idempotency pattern: ADR-004. Part of D1/D2; CS-010 item 4.

## Decision
We will enforce it in sql/004 with two partial unique indexes: `audit_investigation_drafted_once` on `audit(transaction_id) WHERE action='investigation.drafted.v1'`, and `audit_investigation_alert_once` on `audit((inputs->>'alert_key')) WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1')`. Drafted rows carry `alert_key = transaction_id`; the INSERT uses bare `ON CONFLICT DO NOTHING` (no conflict target, covers both indexes); the first writer wins.

## Alternatives rejected
- Pre-check only: a race between two consumers, or between a crash and redelivery, could write both outcomes.

## Consequences
Positive: integrity is a database property independent of process count; replay is a no-op. Negative (cost accepted): a JSON-expression index key (`inputs->>'alert_key'`) is a schema convention that code must always populate; a `model_failure` skip is permanent because it occupies the key (RR-10); duplicate model calls remain possible under a second consumer (RR-14, cost only).

Requirements note: FR-009.7 now names the combined index `audit_investigation_alert_once`; there is no separate skipped-only index. Only authorized writers can occupy these slots (insert guard trigger, ADR-018).

Amendment (skip reasons and alert_key): skip reasons are `{malformed_alert, unknown_transaction, not_alerted, model_failure, grounding_failure}` (`grounding_failure` per ADR-027). `unknown_transaction` and `not_alerted` skips use `alert_key = "alerts:<partition>:<offset>"` (Kafka origin), so a forged alert cannot occupy a real transaction's slot. The investigator acts only when an `alerted.v1` row exists for the transaction (read via `investigator_audit`, ADR-018), and evidence comes from the database, not from the alert payload.

Amendment (keys and nullable columns): `malformed_alert`, `unknown_transaction` and `not_alerted` skips are all keyed by Kafka origin (`alert_key = "alerts:<partition>:<offset>"`), even when the payload parses. For these three, `transaction_id` is NULL. For `model_failure` and `grounding_failure`, `transaction_id` is set and equals `alert_key` (FR-009.7 AC-7). `case_id` is NULL for the three origin-keyed reasons; otherwise it comes from the database `scored.v1` row. W23 is closed for integrity: the indexes enforce exclusivity, leaving only the RR-14 cost.
