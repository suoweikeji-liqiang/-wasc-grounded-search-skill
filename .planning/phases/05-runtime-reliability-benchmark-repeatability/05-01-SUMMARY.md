---
phase: 05-runtime-reliability-benchmark-repeatability
plan: 01
subsystem: api
tags: [runtime-budget, tracing, reliability, fastapi, synthesis]
requires:
  - phase: 04-03
    provides: grounded `/answer` orchestration on the browser-free runtime path
provides:
  - request-scoped runtime budget contract
  - internal runtime trace capture
  - budget-aware answer orchestration
  - cancellation-safe retrieval behavior
affects: [phase-05-benchmarking, repeatability, api-surface]
tech-stack:
  added: []
  patterns: [request-scoped runtime budgets, internal app-state tracing, budget-aware synthesis degradation]
key-files:
  created: [skill/orchestrator/budget.py, tests/test_runtime_budget.py, tests/test_answer_runtime_budget.py]
  modified: [skill/api/entry.py, skill/retrieval/engine.py, skill/synthesis/generator.py, skill/synthesis/orchestrate.py]
key-decisions:
  - "Kept runtime traces internal on `app.state.last_runtime_trace` so benchmark telemetry stays off the public `/answer` schema."
  - "Forwarded remaining synthesis budget as a per-call model timeout instead of relying on the MiniMax client default."
  - "Re-raised `asyncio.CancelledError` in retrieval so cooperative shutdown is not misreported as adapter failure."
patterns-established:
  - "Budget-aware answer execution now returns an internal `AnswerExecutionResult` while the public wrapper still returns `AnswerResponse`."
  - "Budget exhaustion degrades deterministically to `insufficient_evidence` with a `Budget enforcement:` uncertainty note."
requirements-completed: [RELY-01, RELY-03]
duration: 15 min
completed: 2026-04-12
---

# Phase 05 Plan 01: Runtime Budget Summary

**Request-scoped runtime governance for `/answer` with explicit budget enforcement, internal traces, and cancellation-safe retrieval**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-12T18:39:00+08:00 (approx)
- **Completed:** 2026-04-12T18:54:10+08:00
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Added `RuntimeBudget`, `RuntimeTrace`, and `AnswerExecutionResult` as the single runtime-governance contract for the answer path.
- Wired `/answer` through a trace-returning orchestration path that enforces synthesis deadlines and token ceilings without exposing telemetry publicly.
- Tightened retrieval cancellation handling so external cancellation propagates instead of being mislabeled as adapter failure.

## Task Commits

Implementation landed in one commit because task 2 depended directly on the task 1 contracts and both were verified together:

1. **Task 1 + Task 2: runtime budget contracts and answer-path enforcement** - `3931f53` (`feat`)

## Files Created/Modified
- `skill/orchestrator/budget.py` - Request budget, internal trace, and execution result contracts
- `skill/synthesis/orchestrate.py` - Trace-returning answer path, budget-aware degradation, and runtime trace shaping
- `skill/api/entry.py` - `/answer` runtime-budget wiring with internal trace storage on app state
- `skill/retrieval/engine.py` - Cooperative cancellation propagation instead of adapter-error conversion
- `skill/synthesis/generator.py` - Optional per-call timeout override for model generation
- `tests/test_runtime_budget.py` - Runtime budget and trace contract regressions
- `tests/test_answer_runtime_budget.py` - Budget-enforcement, cancellation, and endpoint telemetry regressions

## Decisions Made
- Runtime traces stay internal and are surfaced through benchmark artifacts rather than the public API payload.
- Remaining synthesis budget is enforced at the model-call boundary instead of via a separate watchdog.
- Budget overruns degrade deterministically to `insufficient_evidence` so Phase 5 can measure compliance outcomes instead of uncontrolled waits.

## Deviations from Plan

### Auto-fixed Execution Adjustment

**1. Combined both plan tasks into one green commit**
- **Found during:** Plan 01 TDD cycle
- **Issue:** The runtime budget contract and the answer-path enforcement code are tightly coupled and could not be meaningfully verified in isolation.
- **Fix:** Implemented the contract and its orchestration wiring together, then verified the targeted runtime-budget suite plus the existing answer-path regressions before committing.
- **Files modified:** `skill/orchestrator/budget.py`, `skill/api/entry.py`, `skill/retrieval/engine.py`, `skill/synthesis/generator.py`, `skill/synthesis/orchestrate.py`, `tests/test_runtime_budget.py`, `tests/test_answer_runtime_budget.py`
- **Verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_generator.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py tests/test_runtime_budget.py tests/test_answer_runtime_budget.py -q`
- **Committed in:** `3931f53`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** No scope change. The combined implementation preserved the planned runtime contract while keeping the answer-path regressions green.

## Issues Encountered

None.

## User Setup Required

None - no external service setup changed in this plan.

## Next Phase Readiness

- Benchmark harness work can now consume `app.state.last_runtime_trace` without changing the public `/answer` schema.
- Runtime compliance signals are now available for reporting and repeatability checks in the next plans.

## Self-Check: PASSED

- Verified the Phase 5 runtime-budget suite passes.
- Re-ran the pre-existing answer-path regression files after the runtime changes.
- Verified commit `3931f53` exists in git history.
