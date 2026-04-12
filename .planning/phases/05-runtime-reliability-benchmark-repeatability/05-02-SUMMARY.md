---
phase: 05-runtime-reliability-benchmark-repeatability
plan: 02
subsystem: testing
tags: [benchmark, harness, reporting, cli, repeatability]
requires:
  - phase: 05-01
    provides: internal runtime trace and budget-compliance telemetry on the `/answer` path
provides:
  - locked 10-case benchmark manifest
  - repeatable 10x5 benchmark harness
  - aggregate benchmark summary reports
  - benchmark CLI entrypoint
affects: [phase-05-repeatability, reporting, evaluation-workflow]
tech-stack:
  added: []
  patterns: [manifest-driven benchmark execution, raw-run artifacts plus aggregate summary, live endpoint benchmarking through TestClient]
key-files:
  created: [skill/benchmark/__init__.py, skill/benchmark/models.py, skill/benchmark/harness.py, skill/benchmark/report.py, scripts/run_benchmark.py, tests/fixtures/benchmark_phase5_cases.json, tests/test_benchmark_harness.py, tests/test_benchmark_reports.py]
  modified: [scripts/__init__.py]
key-decisions:
  - "Locked the benchmark manifest in repo fixtures so case ordering and identity stay stable across repeated runs."
  - "Kept raw run logs and aggregate summaries separate so downstream analysis can rely on the preserved ordered run sequence."
patterns-established:
  - "Benchmark execution reuses the live `/answer` path and reads runtime telemetry from `app.state.last_runtime_trace`."
  - "Aggregate benchmark metrics are derived entirely from raw `BenchmarkRunRecord` rows."
requirements-completed: [RELY-02, RELY-03]
duration: 10 min
completed: 2026-04-12
---

# Phase 05 Plan 02: Benchmark Harness Summary

**Locked 10-case benchmark harness with ordered raw run artifacts, aggregate latency/budget summaries, and a user-facing CLI**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-12T18:44:00+08:00 (approx)
- **Completed:** 2026-04-12T18:54:28+08:00
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Added the locked 10-case Phase 5 manifest and strict benchmark case/run/summary contracts.
- Built a 10x5 harness that drives the live `/answer` endpoint through `TestClient` and records per-run latency, token, and budget-compliance metrics.
- Added report generation and a CLI that writes ordered JSONL, CSV, and summary JSON artifacts for the benchmark suite.

## Task Commits

Implementation landed in one commit because the harness, reports, and CLI form one usable benchmark surface:

1. **Task 1 + Task 2: benchmark harness, reports, and CLI** - `56e4340` (`feat`)

## Files Created/Modified
- `tests/fixtures/benchmark_phase5_cases.json` - Locked 10-case benchmark manifest
- `skill/benchmark/models.py` - Strict benchmark contracts
- `skill/benchmark/harness.py` - Ordered 10x5 benchmark runner over `/answer`
- `skill/benchmark/report.py` - Aggregate metrics and artifact writers
- `scripts/run_benchmark.py` - User-facing benchmark CLI
- `tests/test_benchmark_harness.py` - Harness and manifest regressions
- `tests/test_benchmark_reports.py` - Report generation and CLI-default regressions
- `skill/benchmark/__init__.py` - Benchmark package exports
- `scripts/__init__.py` - Python package marker for script-module imports in tests

## Decisions Made
- The manifest is repo-local and versioned so benchmark comparisons stay stable.
- The harness records only raw run rows; aggregate views are computed later from those rows.
- Report writers preserve the input run order exactly so downstream comparisons do not lose temporal ordering.

## Deviations from Plan

### Auto-fixed Issue

**1. [Rule 3 - Blocking] Added `scripts/__init__.py` for test-time CLI imports**
- **Found during:** Task 2 verification
- **Issue:** The CLI-default regression needed to import the script module directly during pytest, but the repo did not yet mark `scripts/` as a Python package.
- **Fix:** Added a minimal `scripts/__init__.py` marker so the script file can be imported consistently in tests.
- **Files modified:** `scripts/__init__.py`
- **Verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_benchmark_harness.py tests/test_benchmark_reports.py -q`
- **Committed in:** `56e4340`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** No scope change. The package marker only removed an import-time blocker for the benchmark CLI regression.

## Issues Encountered

None.

## User Setup Required

None - the CLI uses existing app wiring and local benchmark fixtures.

## Next Phase Readiness

- Repeatability checks can now evaluate grouped benchmark runs instead of hand-auditing raw logs.
- The final endpoint-path regression can exercise the full 10x5 suite against the live `/answer` runtime.

## Self-Check: PASSED

- Verified `tests/test_benchmark_harness.py` and `tests/test_benchmark_reports.py` pass.
- Verified commit `56e4340` exists in git history.
