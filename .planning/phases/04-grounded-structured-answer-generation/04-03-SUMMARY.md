---
phase: 04-grounded-structured-answer-generation
plan: 03
subsystem: api
tags: [answer-api, orchestration, fastapi, retrieval, synthesis]
requires:
  - phase: 04-01
    provides: answer contracts and state mapping
  - phase: 04-02
    provides: prompt builder, generator, citation checker, and uncertainty notes
provides:
  - retrieve-to-answer orchestration
  - browser-free /answer endpoint
  - answer-state downgrade on citation failure
  - endpoint coverage for grounded, insufficient, and retrieval-failure responses
affects: [phase-05-reliability, benchmark-runtime, api-surface]
tech-stack:
  added: []
  patterns: [retrieve-then-synthesize orchestration, retrieval-failure short-circuit, cited-source dedupe by evidence id]
key-files:
  created: [skill/synthesis/orchestrate.py, tests/test_answer_integration.py, tests/test_api_answer_endpoint.py]
  modified: [skill/api/entry.py]
key-decisions:
  - "Short-circuited retrieval_failure before model invocation when no canonical evidence exists."
  - "Filtered final key points and sources to citation-validated content only."
patterns-established:
  - "Answer orchestration starts from execute_retrieval_pipeline and never bypasses canonical evidence."
  - "Endpoint tests assert answer-state visibility and absence of internal telemetry."
requirements-completed: [OUTP-01, OUTP-02, OUTP-03]
duration: 13 min
completed: 2026-04-12
---

# Phase 04 Plan 03: Answer Orchestration Summary

**The browser-free runtime now exposes a grounded `/answer` path that validates citations before declaring success**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-12T08:44:00+08:00
- **Completed:** 2026-04-12T08:57:00+08:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `execute_answer_pipeline()` to compose retrieval, prompt generation, draft parsing, citation validation, uncertainty notes, and final answer-state shaping.
- Added the browser-free `/answer` endpoint on top of the existing route and retrieval stack.
- Added integration and endpoint regressions for grounded success, insufficient evidence, and retrieval failure.

## Task Commits

Implementation landed in one TDD-shaped commit because orchestration behavior and API behavior had to be validated together:

1. **Task 1 + Task 2: answer orchestration and `/answer` endpoint** - `9a49447` (`feat`)

## Files Created/Modified
- `skill/synthesis/orchestrate.py` - end-to-end retrieve-to-answer pipeline
- `skill/api/entry.py` - `/answer` endpoint wiring and default model-client selection
- `tests/test_answer_integration.py` - real synthesis-path orchestration regressions
- `tests/test_api_answer_endpoint.py` - endpoint-level answer-state and contract regressions

## Decisions Made
- Retrieval failure is decided before model invocation when no canonical evidence survives retrieval.
- Final answer sources are deduplicated from validated citations instead of exposing every canonical evidence item.

## Deviations from Plan

### Auto-fixed Execution Adjustment

**1. Combined the two plan tasks into one green commit**
- **Found during:** Wave 3 TDD cycle
- **Issue:** The orchestration path and the `/answer` endpoint share the same final response contract and state transitions.
- **Fix:** Executed the red-green cycle across both tasks, then committed the passing orchestration and endpoint wiring together.
- **Files modified:** `skill/synthesis/orchestrate.py`, `skill/api/entry.py`, `tests/test_answer_integration.py`, `tests/test_api_answer_endpoint.py`
- **Verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q`
- **Committed in:** `9a49447`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** No scope change. The combined commit preserved the intended API and orchestration behavior as one tested unit.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for the offline-tested path.

## Next Phase Readiness

- Phase 5 can now measure grounded answer latency, stability, and budget compliance on a real `/answer` surface.
- The remaining open work for later phases is live MiniMax wiring and runtime reliability tuning, not answer-contract design.

## Self-Check: PASSED

- Verified `tests/test_answer_integration.py` and `tests/test_api_answer_endpoint.py` pass.
- Verified commit `9a49447` exists in git history.
