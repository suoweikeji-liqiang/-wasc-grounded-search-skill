# Retrieval Trace Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add benchmark-only per-source retrieval trace telemetry so timeout-heavy failures can be diagnosed by source, stage, and failure class without changing the public API schema.

**Architecture:** Capture source-level timing and terminal status at the retrieval engine boundary, attach the trace to the internal runtime trace, and serialize it only through benchmark artifacts. Keep `/answer` and `/retrieve` response schemas unchanged.

**Tech Stack:** Python, pytest, FastAPI, pydantic

---

### Task 1: Add failing benchmark/runtime trace regression

**Files:**
- Modify: `tests/test_api_runtime_benchmark.py`
- Modify: `tests/test_benchmark_reports.py`

**Step 1: Write the failing test**

Add coverage that proves benchmark records can carry a `retrieval_trace` payload with per-source entries, and that the public `/answer` payload still does not expose it.

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_api_runtime_benchmark.py tests/test_benchmark_reports.py --import-mode=importlib`

Expected: FAIL because benchmark records and runtime trace do not expose retrieval trace yet.

**Step 3: Write minimal implementation**

Add internal telemetry models and benchmark serialization support only.

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_api_runtime_benchmark.py tests/test_benchmark_reports.py --import-mode=importlib`

Expected: PASS

### Task 2: Capture per-source trace at retrieval engine boundary

**Files:**
- Modify: `skill/retrieval/models.py`
- Modify: `skill/retrieval/engine.py`
- Modify: `skill/orchestrator/budget.py`
- Modify: `skill/synthesis/orchestrate.py`
- Modify: `skill/benchmark/models.py`
- Modify: `skill/benchmark/harness.py`

**Step 1: Write the failing test**

Add a focused engine/runtime test that proves source-level telemetry records:
- `source_id`
- `stage`
- `started_at_ms`
- `elapsed_ms`
- `hit_count`
- `error_class`
- `was_cancelled_by_deadline`

**Step 2: Run test to verify it fails**

Run the focused pytest selection.

Expected: FAIL because source execution results currently do not carry per-source trace data.

**Step 3: Write minimal implementation**

Capture telemetry in `_run_single_source()`, preserve it through `_run_source_variants()` and `_run_first_wave()`, and attach the final trace to internal runtime trace and benchmark records.

**Step 4: Run test to verify it passes**

Run the focused pytest selection.

Expected: PASS

### Task 3: Regression verification and live benchmark trace run

**Files:**
- Modify if needed: `HANDOFF.md`
- Create: `benchmark-results/generated-hidden-like-r1-v46-generalization/`

**Step 1: Run targeted regressions**

Run the focused benchmark/runtime/retrieval tests.

**Step 2: Run full suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`

Expected: PASS

**Step 3: Run one live generalization benchmark**

Run the existing benchmark CLI for `tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization.json`.

Expected: benchmark artifact now includes `retrieval_trace` for each run.

**Step 4: Summarize findings**

Record slow-source distribution and whether policy failures are dominated by registry slowness, fallback slowness, or deadline cancellation.
