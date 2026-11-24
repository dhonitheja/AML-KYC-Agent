# Define Review Checklist — AML-KYC-Agent v0.3.0

The reviewer is `sdlc-define-requirement-reviewer`. Each round is recorded below.

## Round 1 — 2026-11-22 — FAIL

| # | Check | Result | Fix routed to |
|---|---|---|---|
| 1 | Inventory (README, traceability matrix, checklist) | FAIL | orchestrator: files created |
| 2 | Front matter complete, valid focus_track | PASS | — |
| 3 | Source line evidence | FAIL (FR-007.2, FR-005 line ranges) | fr-author |
| 4 | Test files real and actually cover their criteria | FAIL (planned paths in test_files; FR-002/004/005/008, US-001/004/007/009/013, NFR-003 over-claim coverage) | fr, us, nfr authors |
| 5 | Cross-references resolve | PASS | — |
| 6 | Completeness (SDN_FILE has no criterion) | FAIL | fr-author |
| 7 | Quality: FR-009.7 conflicts with the transaction_id FK; FR-010.4 retry loop contradicts US-020 | FAIL | fr-author, us-author |

Warnings sent for fixing:
- W2: Phase 4 clauses in approved NFRs.
- W3: NFR template sections.
- W4: US-014 can't be checked automatically.
- W5: wrong NFR link.
- W6, W7: dedupe key and model_version wording.
- W8, W9: FR-005.3 and FR-006.4 wording.
- W10: duplicate skipped rows.
- W11: unnamed config.
- W12: grammar.

W1 (status values) is answered in [README.md](README.md). W13 (gate-log date) comes from the state script's UTC timestamp, not a defect.

## Round 2 — 2026-11-22 — FAIL

Every round-1 item and warnings W2–W12 are verified fixed. Checks 1, 2, 3, 5 and 6 pass.

| # | Issue | Fix routed to |
|---|---|---|
| 7 | NFR-002 / US-018 promise exactly one narrative per alert, but FR-010.4 allows none after model failure | nfr, us: "at most one drafted; exactly one drafted or skipped record per alert" |
| 7 | The skipped-row dedupe key is NULL for malformed alerts, so it can't deduplicate | fr, us: key on `inputs.alert_key` (transaction id, otherwise `alerts:<partition>:<offset>`) |
| 4 | FR-001.2 and FR-001.3 AC-1 over-claim tests/test_database.py | fr: marked as gaps |

Warnings:
- W14: matrix gaps and NFR/story test columns. Fixed by the orchestrator.
- W15: NFR test_files. Routed to the nfr author.
- W16, W18: routed to the us author.
- W17: the `LLM_MODEL` default. Routed to the fr author.

## Round 3 — 2026-11-22 — FAIL (strike 3, escalated)

All round-2 items and W14–W18 are verified fixed. Checks 1–6 pass.

| # | Issue | Resolution |
|---|---|---|
| 7 | Nothing guarantees each alert ends with exactly one drafted or skipped record. FR-009.5's pre-check ignores skipped rows, so a redelivery after a `model_failure` skip can also produce a draft. NFR-002 says the DB enforces this, which it can't. | User guidance (option 1): the pre-check skips the alert when either a drafted row for its transaction_id or a skipped row for its alert_key exists. NFR-002 is reworded to "each unique-indexed; the pre-check makes them mutually exclusive". |

Warnings:
- W19: FR-001 duplicate traceability rows. Routed to the fr author.
- W20: NFR-001 repeated sentence. Routed to the nfr author.
- W21: US-018 AC order. Routed to the us author.
- W22: `claude-sonnet-5-5` is a current model id. No change needed.

The loop counter was reset after the user's guidance.

## Round 4 — 2026-11-22 — PASS

All seven checks pass, with no regressions. The reviewer withdrew W19 and W20; both were misreadings in its round-3 pass, and the documents were correct.

Open warning carried to Design:
- W23: the FR-009.5 pre-check (read, then write) keeps drafted and skipped rows mutually exclusive only while the investigator handles one alert at a time. That holds today because `alerts` has one partition (compose.yaml:14). Adding partitions or consumers would need an atomic mechanism.

Awaiting user sign-off.
