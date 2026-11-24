---
id: "NFR-003"
title: "Least privilege and append-only audit"
type: "nonfunctional"
category: "security"
focus_track: "security"
priority: "P0"
status: "approved"
version: "1.1"
created: "2026-11-22"
author: "requirement-author-agent"
reviewer: "requirement-reviewer-agent"
source_files: ["sql/001-foundations.sql", "sql/003-kyc.sql", "compose.yaml", "watchlist.py", "requirements.txt"]
test_files: []
verification_method: "code-review"
---

# NFR-003: Least privilege and append-only audit

Focus track: security (ISO/IEC 27001).

## Description
The app role holds only SELECT/INSERT so the audit trail is append-only; the API is loopback-bound, XML is parsed safely and dependencies are version-bounded.

## Requirements
- The app role `aml_worker` SHALL hold only SELECT/INSERT; no UPDATE/DELETE (`sql/001-foundations.sql:21-23`, `sql/003-kyc.sql:10`). Code MUST NOT UPDATE or DELETE `audit`. The role cannot INSERT into `cases`.
- The API SHALL bind only to loopback: `127.0.0.1:8000:8000` (`compose.yaml:61`).
- Watchlist XML SHALL be parsed with `defusedxml` (`watchlist.py:13`); the watchlists mount for the API is read-only.
- Dependencies SHALL be version-bounded in `requirements.txt` (exact pins for `psycopg==3.2.6`, `quixstreams==3.15.0`, `defusedxml==0.7.1`; range bounds for the rest).
- (Phase 4, FR-009/FR-010, built) Phase 4 SHALL run under a database role holding no more than SELECT on `transactions` and `audit` and INSERT on `audit`, and SHALL NOT be able to write audit rows for actions other than its own `investigation.*.v1` actions. Conversely, no other role SHALL be able to write `investigation.*` rows or rows with actor `investigator-v1`. The role choice is recorded in a Design ADR. Any new role or grants SHALL be created only via an idempotent migration (`IF NOT EXISTS`, re-run every startup) added to the `migrate` command. (Amended 2026-11-22 at Design, per the user's finance-security direction.)

## Verification Method
Code review citing `sql/001-foundations.sql:21-23` and `sql/003-kyc.sql:10` (grants), `compose.yaml:61` (loopback bind), `watchlist.py:13` (defusedxml) and `requirements.txt` (bounds). No automated privilege test yet (gap).

Related: FR-008, FR-009.

## Change Notes
- v1.1: Design amendment (2026-11-22): Phase 4 runs under a dedicated least-privilege database role, plus a reverse guard (no other role may write `investigation.*` rows or rows with actor `investigator-v1`).
