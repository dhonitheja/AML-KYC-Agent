---
id: "ADR-028"
title: "Network segmentation and closed egress list"
type: "adr"
status: "accepted"
version: "1.0"
created: "2026-11-23"
author: "adr-author-agent"
supersedes: []
superseded_by: ""
satisfies_nfr: ["NFR-008", "NFR-006"]
focus_track: "security"
evidence: "documented"
---

# ADR-028: Network segmentation and closed egress list

## Status
Accepted by the user at the Design sign-off (2026-11-24, NFR-008 delta).

## Context
NFR-008 (v1.1) requires customer data to stay inside the Compose deployment, with a closed egress list (NFR-008.3) and no host exposure except loopback `api` (NFR-008.2). Today everything shares the default Compose network, and `ingest` downloads the OFAC list (watchlist.py) from a container that also holds the DB DSN and Kafka access. Docker networks can filter by network, not by hostname. Redpanda in dev-container mode also tries to send usage statistics. Sources: NFR-008, ARCH-001 section 1a, B9, B17, B18, RR-23.

## Decision
We will declare three Compose networks and place services by membership (ARCH-001 section 1a):
- `internal` (`internal: true`, no gateway): postgres, redis, kafka, topic, migrate, scorer, ingest, investigator, llm (ADR-029), and api.
- `ingress` (ordinary bridge): `api` only, solely to publish `127.0.0.1:8000`. `postgres`, `redis`, `kafka` publish no ports.
- `egress` (ordinary bridge): `watchlist-fetch` only by default (anthropic mode adds `investigator`, ADR-030).

We will move the OFAC download out of `ingest` into a dedicated one-shot `watchlist-fetch` service: Compose profile `fetch` (never starts by default), `egress` only and not on `internal`, no secrets, no DB connection, and its only write mount is `./watchlists` (read-only for api and scorer). Parse and integrity checks stay as in ADR-010.

We will keep `api` with its technical outbound route through `ingress` and record it as accepted residual risk RR-23, controlled by the NFR-008 AC-5 grep (no outbound calls in api code), non-root user (ADR-026) and no secrets.

We will disable Redpanda usage telemetry explicitly in the `kafka` command; the exact flag is verified against the pinned v24.3.10 image in Develop, so the intent is in config and not only implied by network state.

Compliance is reviewed with `docker compose config` (NFR-008 AC-2, AC-7, AC-8) and in-container connection tests (AC-1, AC-6, AC-8).

## Consequences
Positive: no data-holding service can reach the internet even if its code or dependencies are compromised (NFR-008.1); the only internet-facing fetcher has nothing to steal and cannot reach postgres; the check is a static config review.

Negative: RR-23 stays open for `api`; image pulls and the OFAC fetch become explicit deploy-time steps (`docker compose --profile fetch run watchlist-fetch`); the `CLAUDE.md`, README and CI OFAC commands (currently `watchlist.py` through `ingest`) must change, owned by Develop, and PLAN-001 must be revised for this delta before Develop starts; a new service and two networks to maintain; the Redpanda flag may differ by version.

Rejected alternative: an `ingress` proxy container in front of an internal-only `api`, which removes the api route entirely. Cost accepted instead: RR-23 (a compromised `api` could use its route), to avoid an extra hop and service in a loopback demo. Also rejected: keeping the OFAC download in `ingest`, which leaves a DB- and Kafka-connected container with an internet route.

Relations: extends ADR-012 (loopback API, unchanged) and ADR-010 (snapshot integrity, unchanged); ADR-026 applies to the new service. Satisfies NFR-008.1, NFR-008.2, NFR-008.3(b)/(c)/(d)/(e); supports NFR-006.
