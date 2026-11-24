# Security Policy

## System and trust boundaries

The supported demo runs locally with synthetic identities and payments. Compose publishes FastAPI on host loopback. Review onboarding and read routes, Redpanda producers and consumers, Redis velocity state, PostgreSQL migrations and roles, and watchlist loading. For revisions containing the Phase 4 investigator, include model adapters, evaluation tools, container images, secret mounts and Compose overrides. State which revision and deployment mode a finding affects.

Treat API payloads, broker messages, downloaded watchlists, free-text evidence and model responses as untrusted. The operator controls deployment and migrations. An internal service can reach peers on its network, so network membership alone cannot establish a sender's identity or grant database authority.

## Required properties

- **Audit integrity and replay.** Persist transaction and audit records before acknowledging offsets. Replays must preserve the original decision and evidence. Runtime roles must be unable to alter or erase audit history or impersonate another audit writer. Reusing an onboarding ID with different input must preserve the original application.
- **Investigation authority.** Bind each alert to the corresponding persisted alert decision before calling a model. Build evidence from records for the authorized transaction and account. Retries and concurrent delivery must yield at most one terminal investigation outcome per alert. The investigator's image, environment and mounts must expose only the credentials it needs.
- **Data egress.** Treat unset classification as customer data. Stub and local investigation must stay offline or on the internal network. An egress-enabled investigation requires explicit Anthropic mode and synthetic classification before reading the provider key or sending evidence. Assess effective routes and destinations across combined Compose files. The watchlist downloader needs outbound access without access to customer stores.
- **Human disposition.** Screening hits are candidates for review. Model drafts must carry evidence citations and human-review labels. Neither untrusted evidence nor generated text may authorize a transfer, change a score, or dispose of a case.
- **Input and provenance.** Parse watchlist XML safely, validate replacements before activation, and retain the snapshot identifier with findings. Bound model inputs, outputs and retries. Keep credentials and unnecessary identity data out of prompts, reports and runtime logs.

## Findings and limitations

Describe the input or role, reachable service, deployment prerequisites, affected data or state, and consequence. Give greatest weight to customer-data disclosure, privilege escalation, audit forgery or erasure, and unauthorized financial or case actions. For availability findings, distinguish a rejected event from a stalled consumer or loss of durable work. Check fresh and upgraded volumes when a finding depends on grants, triggers or broker settings.

The [README residual-risk register](README.md#residual-risks-accepted-for-the-synthetic-demo) documents narrowly scoped demo assumptions. For example, a forged alert can produce a bounded skip record. A model call or draft based on that alert exceeds the stated acceptance. Grounding checks cover only some claims and depend on human review. Reassess any changed exposure, data class or consequence. This policy adds no exclusions or production risk acceptance.
