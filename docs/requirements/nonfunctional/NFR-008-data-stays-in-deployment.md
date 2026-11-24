---
id: "NFR-008"
title: "Customer data stays inside the deployment"
type: "nonfunctional"
category: "privacy"
focus_track: "security"
priority: "P0"
status: "approved"
version: "1.2"
created: "2026-11-23"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["compose.yaml", "compose.anthropic.yaml", "llm.Dockerfile", "Dockerfile", "investigator.py", "watchlist.py", ".github/workflows/ci.yml"]
test_files: ["tests/test_investigator.py", "tests/test_egress_static.py", "tests/compose_check.py", "tests/egress_check.py", "tests/conftest.py"]
verification_method: "test"
---

# NFR-008: Customer data stays inside the deployment (Phase 4, built)

Focus track: security (ISO/IEC 27001 confidentiality; GLBA safeguards). Also AI governance for Phase 4.

## Description
Customer data (transactions, accounts, counterparties, screening results, audit rows and any evidence or narrative derived from them) SHALL NOT leave the Docker Compose deployment. No service and no agent may pass it to a third party, another agent or the internet. The only exceptions are the closed list in NFR-008.3, and none of them carries customer data. This is a product owner directive, added 2026-11-23 after Define and Design sign-off.

## Requirements

### NFR-008.1: No outbound route for data-holding services
Every runtime service that stores or processes customer data SHALL be attached only to an internal network (Docker `internal: true`) with no route outside the deployment. These services are `postgres`, `redis`, `kafka`, `topic`, `migrate`, `scorer`, `ingest`, `investigator` and the self-hosted model server (FR-010.5). `api` is attached to the internal network and, only to publish its loopback port, to one non-internal ingress network (NFR-008.3(e)). The self-hosted model server SHALL NOT download model weights at runtime; weights are baked into its image or loaded from a local volume. The exceptions are listed in NFR-008.3.

### NFR-008.2: No host exposure except the loopback API
Only `api` SHALL publish a host port, bound to `127.0.0.1` (unchanged, `compose.yaml:61`). `postgres`, `redis` and `kafka` SHALL NOT publish host ports.

### NFR-008.3: Closed list of permitted egress
Only these outbound paths are permitted, and none of them may carry customer data:
- (a) The investigator in `anthropic` mode, and only when the deployment is declared synthetic (`DATA_CLASSIFICATION=synthetic`, FR-010.6). Otherwise anthropic mode SHALL refuse to start.
- (b) The one-shot OFAC list download (`watchlist.py`). It SHALL run in a dedicated one-shot service (e.g. `watchlist-fetch`, behind a Compose profile so it never starts by default), not in `ingest`. That service is attached only to an egress network, is not attached to the internal network, has no secrets, and has a write mount limited to `./watchlists`. It fetches public data with an HTTP GET, sends no customer data and opens no database connection.
- (c) Image build, including `pip install` in the app Dockerfile and the model weights pulled at build time in `llm.Dockerfile` (ADR-029). It runs at build time, when no customer data exists.
- (d) Image pulls by the Docker engine at deploy time (redpanda, postgres/pgvector, redis, the model-server image). The engine pulls images; no container sends data.
- (e) Inbound loopback ingress to `api` on `127.0.0.1:8000`. `api` needs a non-internal network to publish this port, which also gives it a technical outbound route. Residual risk: `api` code makes no outbound calls (verified by AC-5's grep scope), and Design SHALL record this as a residual risk with any mitigation.

Any new egress path SHALL require a new ADR and an amendment to this list.

### NFR-008.4: Agents do not forward data
The investigation agent (FR-009) SHALL pass customer data only to the database and to its configured model backend: the in-process stub, the in-deployment model server, or Anthropic under NFR-008.3(a). It SHALL NOT forward evidence or narratives to any other agent, service, Kafka topic, file or log. Log lines SHALL carry only the transaction id or alert_key, the outcome, attempt count and latency (FR-009, CS-008).

### NFR-008.5: Development agents see synthetic data only
Coding and SDLC agents working on this repository SHALL work only with repository content and synthetic data. They SHALL NOT be given credentials, connection strings or exports for any deployment that holds real customer data.

## Acceptance Criteria
- AC-1: From inside the `investigator` container in `stub` mode, a TCP connection to an external host (e.g. `api.anthropic.com:443`) fails. The same check fails from the `scorer` container.
- AC-2: `docker compose config` shows no `ports` entry on `postgres`, `redis` or `kafka`, and `api` is published only on `127.0.0.1`.
- AC-3: `LLM_MODE=anthropic` with `DATA_CLASSIFICATION` unset, or set to any value other than `synthetic`, exits non-zero at startup before the API key is read and before any network connection is opened (FR-010.6).
- AC-4: Investigator log output for a drafted alert and for a skipped alert contains no counterparty name and no amount from the evidence (log assertion on captured output).
- AC-5: `watchlist.py` imports no database module and issues only HTTP GET requests, and no other runtime module (`api.py`, `pipeline.py`, `scoring.py`, `kyc.py`, `rules.py`) makes an outbound network call (code review plus grep for `urllib`, `requests`, `httpx`, `socket` and network SDK imports such as `anthropic`).
- AC-6: With `LLM_MODE=local`, a TCP connection from the `investigator` container to an external host fails, while a request to the in-deployment model server succeeds.
- AC-7: `docker compose config` shows every service listed in NFR-008.1 attached only to the internal network, except `api`, which is also attached to the ingress network and nothing else.
- AC-8: The OFAC fetch service is not attached to the internal network, and from inside it a connection to `postgres:5432` fails.

## Verification Method
In-container probes (`tests/egress_check.py`, CI) cover AC-1 and AC-8; the same probe in the opt-in `local-model` job covers AC-6. `tests/compose_check.py` over `docker compose config` (CI) covers AC-2, AC-7 and the network half of AC-8. Pure `load_config`/`main()` tests cover AC-3, a log-assertion test covers AC-4, `tests/test_egress_static.py` covers AC-5, and review covers NFR-008.5.

Related: NFR-003, NFR-006, FR-009, FR-010, ADR-015, ADR-019, ADR-020.

## Change Notes
- v1.2 (2026-11-24, Requirements Sync, PLAN-002): built. NFR-008.3(c) widened to name the build-time model-weights download in `llm.Dockerfile` (ADR-029); no new runtime egress path. AC verification: AC-1, AC-2, AC-7, AC-8 by the CI tools `tests/egress_check.py` and `tests/compose_check.py` (not pytest); AC-3, AC-4 by tests/test_investigator.py; AC-5 by tests/test_egress_static.py; AC-6 ONLY by the opt-in `local-model` workflow_dispatch job (its network half runs every push via AC-1). Whether the `llm` container runs as uid 10001 is not asserted (RR-25).
- v1.1 (2026-11-23, gate round 7): `api` ingress network and exception (e) with residual risk; OFAC fetch moved to a dedicated one-shot service; image pulls (d) and no-runtime-weights rule added; AC-5 widened; AC-7, AC-8 added.
- v1.0: New (2026-11-23). Product owner directive: customer data must not leave the database, the server or the ingestion path, and agents must not leak it to other agents.
