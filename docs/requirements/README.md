# Requirements — AML-KYC-Agent v0.3.0

| Folder | Contents | Count |
|---|---|---|
| `functional/` | FR-001..FR-011 | 11 |
| `nonfunctional/` | NFR-001..NFR-008 | 8 |
| `user-stories/` | US-001..US-029 | 29 |

- [traceability-matrix.md](traceability-matrix.md): requirement → story → test mapping and known gaps.
- [review-checklist.md](review-checklist.md): Define gate results.
- `sdlc-metadata.yml`: lifecycle state, owned by the SDLC state script. Don't edit it by hand.

## Status values

- `implemented`: the FR describes behavior already in the code (Phases 1–4), with file:line evidence. FR-009, FR-010 and FR-011 were promoted from `proposed` on 2026-11-24 (PLAN-002).
- `approved`: the NFR or user story is accepted and the behavior exists. NFR-008 and US-016..US-029 were promoted on 2026-11-24 (PLAN-002). Some acceptance criteria are verified only by CI tools or the opt-in `local-model` job, see the matrix.
- `proposed`: the behavior isn't built yet. Nothing is proposed today; draft requirements from feature-intake start here.

## Scope

Phase 4 adds an investigation agent that consumes the `alerts` topic and writes one recommend-only `investigation.drafted.v1` narrative per alert. By default it runs with a deterministic stub model, so no credentials are needed. Linking onboarding KYC to accounts is out of scope.
