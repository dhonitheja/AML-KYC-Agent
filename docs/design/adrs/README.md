# Architecture Decision Records

| ADR | Title | Status | Supersedes | Satisfies NFR |
|-----|-------|--------|------------|---------------|
| [ADR-001](ADR-001-redpanda-kafka-broker.md) | Redpanda as the Kafka broker | accepted | - | NFR-001, NFR-007 |
| [ADR-002](ADR-002-account-keyed-single-partition-topics.md) | Account-keyed single-partition topics | superseded | ADR-033 | NFR-001, NFR-002 |
| [ADR-003](ADR-003-postgres-audit-system-of-record.md) | Postgres audit table as system of record, append-only via grants | accepted | - | NFR-003, NFR-004 |
| [ADR-004](ADR-004-idempotency-uuid5-on-conflict-unique-indexes.md) | Idempotency via uuid5 ids, ON CONFLICT and partial unique indexes | accepted | - | NFR-002 |
| [ADR-005](ADR-005-offset-commit-after-db-commit.md) | Kafka offset commit after DB commit | accepted | - | NFR-002 |
| [ADR-006](ADR-006-quix-scorer-confluent-ingest.md) | Quix Streams for the scorer, confluent_kafka for ingest | superseded | ADR-032 | NFR-001, NFR-002 |
| [ADR-007](ADR-007-redis-lua-event-time-velocity.md) | Redis Lua event-time velocity windows | accepted | - | NFR-001, NFR-002 |
| [ADR-008](ADR-008-pure-rules-engine.md) | Pure rules engine | accepted | - | NFR-001, NFR-004 |
| [ADR-009](ADR-009-versioned-audit-action-names.md) | Versioned audit action names | accepted | - | NFR-004 |
| [ADR-010](ADR-010-defusedxml-sha256-sdn-snapshots.md) | defusedxml parsing with SHA-256 SDN snapshots | accepted | - | NFR-004, NFR-006 |
| [ADR-011](ADR-011-rapidfuzz-threshold-88.md) | RapidFuzz threshold 88 with token-sorted normalization | accepted | - | NFR-001, NFR-004 |
| [ADR-012](ADR-012-fastapi-loopback-no-auth.md) | FastAPI on loopback, no authentication | accepted | - | NFR-003, NFR-006 |
| [ADR-013](ADR-013-hard-coded-config-sdn-file-only.md) | Hard-coded configuration, SDN_FILE the only environment variable | accepted | - | NFR-006, NFR-007 |
| [ADR-014](ADR-014-idempotent-migrations-every-startup.md) | Idempotent migrations re-run on every startup | accepted | - | NFR-002, NFR-007 |
| [ADR-015](ADR-015-synthetic-data-only.md) | Synthetic data only | accepted | - | NFR-006 |
| [ADR-016](ADR-016-recommend-only-posture.md) | Recommend-only posture | accepted | - | NFR-005 |
| [ADR-017](ADR-017-investigator-process-model.md) | Investigator process model | accepted | - | NFR-001, NFR-002, NFR-005 |
| [ADR-018](ADR-018-dedicated-investigator-role-and-view.md) | Dedicated aml_investigator role, investigator_audit view and insert guard trigger | accepted | - | NFR-003, NFR-005, NFR-006 |
| [ADR-019](ADR-019-untrusted-input-and-output-handling.md) | Untrusted-input and output handling for the model call | accepted | - | NFR-005, NFR-006 |
| [ADR-020](ADR-020-data-minimization-allow-list-alias.md) | Data minimization allow-list, SUBJECT_ACCOUNT alias and stored payload hash | accepted | - | NFR-004, NFR-006 |
| [ADR-021](ADR-021-secrets-via-docker-secret-files.md) | Secrets via Docker secret files with env fallback and sanitized errors | accepted | - | NFR-006 |
| [ADR-022](ADR-022-anthropic-sdk-pinned-own-retry.md) | Anthropic SDK, exact pin, own retry, deterministic parameters and recorded versions | accepted | - | NFR-004, NFR-005, NFR-006, NFR-007 |
| [ADR-023](ADR-023-draft-skip-mutual-exclusion-index.md) | Draft/skip mutual exclusion via combined partial unique index | accepted | - | NFR-002, NFR-004 |
| [ADR-024](ADR-024-audit-immutability-triggers.md) | Audit immutability triggers blocking UPDATE, DELETE and TRUNCATE | accepted | - | NFR-003, NFR-004 |
| [ADR-025](ADR-025-audit-retention-and-residual-risk.md) | Audit retention of at least five years, no deletion path, residual-risk register | accepted | - | NFR-004, NFR-006 |
| [ADR-026](ADR-026-non-root-container-user.md) | Non-root container user for all services | accepted | - | NFR-003, NFR-006 |
| [ADR-027](ADR-027-hallucination-grounding-controls.md) | Hallucination and grounding controls for drafted narratives | accepted | - | NFR-004, NFR-005 |
| [ADR-028](ADR-028-network-segmentation-closed-egress.md) | Network segmentation and closed egress list | accepted | - | NFR-006, NFR-008 |
| [ADR-029](ADR-029-self-hosted-model-backend.md) | Self-hosted model backend (LLM_MODE=local) | accepted | - | NFR-005, NFR-006, NFR-008 |
| [ADR-030](ADR-030-synthetic-data-gate-external-provider.md) | Synthetic-data gate for the external model provider | accepted | - | NFR-005, NFR-006, NFR-008 |
| [ADR-031](ADR-031-analyst-console-basic-auth.md) | Analyst console with HTTP Basic auth from a secret file | accepted | - | NFR-003, NFR-005 |
| [ADR-032](ADR-032-batched-confluent-scorer.md) | Batched confluent_kafka scorer with one DB transaction per poll | accepted | - | NFR-001, NFR-002, NFR-009 |
| [ADR-033](ADR-033-partitioned-transactions-topic.md) | Account-keyed 16-partition transactions topic with scorer replicas | accepted | - | NFR-001, NFR-002, NFR-009 |

ADR-001..016 are retroactive records of decisions already in the code (`accepted`). ADR-017..027 were new in the Design phase and were accepted by the user at the Design sign-off (2026-11-23). ADR-028..030 are the NFR-008 delta, accepted by the user at the Design sign-off (2026-11-24), with the ADR-013, ADR-015 and ADR-022 amendments. ADR-031 (analyst console auth) was accepted at the Phase 5 sign-off (2026-11-24). ADR-032 and ADR-033 (Phase 6 throughput) were accepted at the Phase 6 design check (2026-11-24) and supersede ADR-006 and ADR-002. See `../design-traceability.md` for the ADR to NFR and component mappings.

## How to write a new ADR

Copy any file here, take the next free number (`ADR-034`), and keep one decision per file. Use the five sections of Michael Nygard's format ("Documenting Architecture Decisions", 2011): Status, Context (the forces and sources), Decision ("We will ..."), Consequences (what gets easier and harder, naming NFRs), and for contentious choices add the alternatives rejected and the cost accepted. A decision already in code is `accepted` with an evidence tag; a new one starts `proposed`. To replace an ADR, write a new one with `supersedes: [ADR-OLD]` and set the old one to `status: superseded` with `superseded_by: "ADR-NEW"`. Add the row to this index.
