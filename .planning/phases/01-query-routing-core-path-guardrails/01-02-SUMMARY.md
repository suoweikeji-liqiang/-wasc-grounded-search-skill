---
phase: 01-query-routing-core-path-guardrails
plan: 02
subsystem: testing
tags: [python, pytest, fastapi, testclient, cli, routing]
requires:
  - phase: 01-query-routing-core-path-guardrails
    provides: deterministic classifier, route planner, and POST /route contract from Plan 01
provides:
  - Offline fixture-backed regression coverage for policy/academic/industry/mixed routing behavior
  - API contract assertions for concrete-primary mixed fallback and browser-free invariants
  - CLI smoke command that emits the same structured route metadata as the API
affects: [phase-02-retrieval-routing]
tech-stack:
  added: []
  patterns:
    - fixture-driven routing contract tests
    - offline TestClient verification against FastAPI boundary
    - argparse-based smoke entrypoint for deterministic route metadata
key-files:
  created:
    - tests/fixtures/phase1_queries.json
    - tests/test_route_contracts.py
    - scripts/route_query.py
  modified: []
key-decisions:
  - "Kept ambiguous mixed outputs user-visible as route_label=mixed while enforcing concrete primary_route and null supplemental_route."
  - "Validated source_families against concrete primary route tables for ambiguous mixed scenarios."
  - "Kept all verification offline with no network/provider/browser dependencies."
patterns-established:
  - "Routing fixtures are the single truth source for contract regressions."
  - "API and CLI paths share the same classify_query -> plan_route semantics."
requirements-completed: [ROUT-01, ROUT-02, ROUT-03]
duration: 17m
completed: 2026-04-11
---

# Phase 1 Plan 02: Offline Routing Validation Summary

**Fixture-driven offline pytest contracts and a CLI smoke tool now prove deterministic routing guardrails, mixed fallback semantics, and browser-free behavior for Phase 1.**

## Performance

- **Duration:** 17m
- **Started:** 2026-04-11T09:31:00Z
- **Completed:** 2026-04-11T09:48:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added a representative routing fixture matrix covering normal routes, explicit mixed, short-query mixed, low-signal mixed, precedence conflicts, and all-weak/tie fallback.
- Added offline `pytest` regression coverage using `FastAPI TestClient` to enforce exact `/route` response shape and guardrail semantics.
- Added an `argparse`-based CLI smoke path that emits the same public routing contract with `browser_automation` fixed to `disabled`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create fixture coverage for normal routes, precedence conflicts, and mixed guardrails** - `6e0a487` (feat)
2. **Task 2: Add pytest regression coverage for route contracts and browser-free behavior** - `71d7412` (test)
3. **Task 3: Add a CLI smoke entrypoint for structured routing output** - `b64db3e` (feat)

## Files Created/Modified
- `D:/study/WASC/.claude/worktrees/agent-ab8d73ef/tests/fixtures/phase1_queries.json` - Offline routing fixture matrix for Phase 1 contract scenarios.
- `D:/study/WASC/.claude/worktrees/agent-ab8d73ef/tests/test_route_contracts.py` - Fixture-parameterized API contract and guardrail regression suite.
- `D:/study/WASC/.claude/worktrees/agent-ab8d73ef/scripts/route_query.py` - Offline CLI smoke tool outputting schema-compatible route JSON.

## Decisions Made
- Enforced the ambiguous mixed contract explicitly in tests: `route_label` remains `mixed`, `primary_route` is concrete, `supplemental_route` is `null`, and `source_families` derive from the concrete primary route.
- Kept response-key assertions exact to lock the public API/CLI contract for downstream phases.
- Preserved offline-only validation boundaries to satisfy Phase 1 stability and browser-free constraints.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## Known Stubs
None.

## Threat Flags
None.

## Next Phase Readiness
- Phase 2 retrieval work can rely on stable, regression-protected route metadata from both API and CLI entrypoints.
- Guardrails for short/low-signal ambiguity and precedence fallback are now continuously testable offline.

## Self-Check: PASSED
- FOUND: tests/fixtures/phase1_queries.json
- FOUND: tests/test_route_contracts.py
- FOUND: scripts/route_query.py
- FOUND: .planning/phases/01-query-routing-core-path-guardrails/01-02-SUMMARY.md
- FOUND: 6e0a487
- FOUND: 71d7412
- FOUND: b64db3e
