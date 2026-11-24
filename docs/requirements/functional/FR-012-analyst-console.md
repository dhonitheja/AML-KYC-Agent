---
id: "FR-012"
title: "Analyst console and disposition recording"
type: "functional"
priority: "P1"
status: "implemented"
version: "1.0"
created: "2026-11-24"
author: "requirement-author-agent"
reviewer: ""
source_files: ["api.py", "console.html", "sql/005-console.sql", "compose.yaml"]
test_files: ["tests/test_console.py"]
depends_on: ["FR-004", "FR-009"]
implements: []
---

# FR-012: Analyst console and disposition recording

## Description
A browser console served by the API at `/console` lets named analysts review alerts with the investigator draft and record one human disposition per alert in `audit`. It closes RR-4. Nothing in it changes `cases`, blocks a payment or files a report (ADR-016).

## Requirements

### FR-012.1: Authenticated access
`/console`, `/console/queue` and `/console/decisions` SHALL require HTTP Basic credentials that match a line `name:password` in the `analysts` secret file. Names match `[a-z0-9_.-]{1,64}`. A missing file means no analyst can sign in. (ADR-031)

**Acceptance Criteria:**
- AC-1: No credentials, a wrong password or an unknown name gets 401 on every console route.
- AC-2: Valid credentials get the console page.

### FR-012.2: Work queue
`GET /console/queue` SHALL return the newest 100 `alerted.v1` alerts that have no decision, each with the transaction, the alert rules, and the `investigation.drafted.v1` draft or skip reason when present.

**Acceptance Criteria:**
- AC-1: A new alert is listed with its score and no draft until the investigator writes one.
- AC-2: A decided alert is no longer listed.

### FR-012.3: Record a disposition once
`POST /console/decisions` with JSON `{transaction_id, disposition, rationale}` SHALL append one `analyst.decided.v1` audit row with `actor=analyst:<name>`, the case ID from the alert, and `inputs` holding the body, the analyst name from authentication and the draft `event_id` the analyst had available. `disposition` is `escalate`, `close_no_action` or `request_information`; `rationale` is 10 to 2000 characters.

**Acceptance Criteria:**
- AC-1: The first decision returns 200 and writes exactly one row; a second decision by anyone returns 409.
- AC-2: An unknown transaction returns 404. An invalid disposition, a short rationale or extra fields such as `analyst` return 422.
- AC-3: A non-JSON body is refused (CSRF), and no row is written for any refused request.
