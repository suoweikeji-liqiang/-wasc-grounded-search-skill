---
phase: 05-runtime-reliability-benchmark-repeatability
plan: 03
subsystem: testing
tags: [repeatability, benchmark, fastapi, endpoint-regression, reliability]
requires:
  - phase: 05-01
    provides: runtime trace and budget-compliance signals on `/answer`
  - phase: 05-02
    provides: locked benchmark manifest and ordered run-record/report pipeline
provides:
  - grouped repeatability evaluation
  - end-to-end endpoint-path benchmark regression
  - deterministic repeatability proof for the offline suite
affects: [phase-05-verification, benchmark-validation]
tech-stack:
  added: []
  patterns: [grouped-case repeatability scoring, deterministic live-app benchmark regression]
key-files:
  created: [skill/benchmark/repeatability.py, tests/test_benchmark_repeatability.py, tests/test_api_runtime_benchmark.py]
  modified: []
key-decisions:
  - "Defined repeatability from grouped run invariants instead of from aggregate averages alone."
  - "Kept the final benchmark regression on `skill.api.entry.app` so the test covers the real `/answer` path."
patterns-established:
  - "Repeatability is evaluated per case from run count, status stability, route stability, latency spread, and budget pass rates."
  - "Endpoint benchmark regressions inject deterministic app-state adapters and model behavior rather than bypassing the FastAPI entrypoint."
requirements-completed: [RELY-01, RELY-02, RELY-03]
duration: 8 min
completed: 2026-04-12
---

# Phase 05 Plan 03: Repeatability Summary

**Grouped repeatability evaluation and live `/answer` benchmark regression that prove stable 10x5 execution without leaking telemetry publicly**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-12T18:46:00+08:00 (approx)
- **Completed:** 2026-04-12T18:54:48+08:00
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added grouped repeatability evaluation for benchmark run records with explicit pass/fail invariants.
- Added an endpoint-path benchmark regression that runs the full 10-case x 5-run suite through the live FastAPI app.
- Proved the deterministic offline benchmark keeps telemetry internal while still producing repeatable run and summary artifacts.

## Task Commits

Implementation landed in one commit because the repeatability evaluator and endpoint benchmark regression validate the same artifact stream:

1. **Task 1 + Task 2: repeatability evaluator and endpoint benchmark regression** - `64342ca` (`test`)

## Files Created/Modified
- `skill/benchmark/repeatability.py` - Grouped run evaluator for repeatability verdicts
- `tests/test_benchmark_repeatability.py` - Repeatability pass/fail regressions
- `tests/test_api_runtime_benchmark.py` - Live-app 10x5 benchmark regression over `/answer`

## Decisions Made
- Repeatability is judged from explicit grouped invariants rather than from one-off happy-path runs.
- The end-to-end benchmark regression stays on the real FastAPI surface and uses app-state fakes only for deterministic runtime behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - the deterministic endpoint-path benchmark uses local fakes and no extra credentials.

## Next Phase Readiness

- Phase 5 now has enough automated evidence to close the roadmap phase, provided the verification artifact is written and tracking files are updated.
- Future tuning can use the benchmark CLI and report artifacts without changing the public API contract.

## Self-Check: PASSED

- Verified `tests/test_benchmark_repeatability.py` and `tests/test_api_runtime_benchmark.py` pass.
- Verified the full repo suite passes after the endpoint benchmark regression was added.
- Verified commit `64342ca` exists in git history.
