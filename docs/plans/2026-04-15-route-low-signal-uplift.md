# Route Low-Signal Uplift Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce benchmark misses caused by low-signal or tied routing by expanding route marker coverage and improving cross-domain detection for combined policy/industry/academic queries.

**Architecture:** Keep the deterministic rule-first classifier but patch the specific failure clusters revealed by `v31`: missing academic technical terms, missing official/policy acronyms, missing multilingual policy markers, and under-detected cross-domain combination phrasing. Validate through focused routing tests before re-benchmarking.

**Tech Stack:** Python, pytest, FastAPI test client

---

### Task 1: Add failing routing regressions

**Files:**
- Modify: `tests/test_intent_task2.py`
- Modify: `tests/test_route_contracts.py`

**Step 1: Add intent-level regressions for current misrouted benchmark-style queries**

**Step 2: Run the focused intent tests and verify failure**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_intent_task2.py tests/test_route_contracts.py --import-mode=importlib`
Expected: FAIL on the new low-signal and mixed-detection cases.

### Task 2: Expand route markers and mixed detection

**Files:**
- Modify: `skill/config/routes.py`
- Modify: `skill/orchestrator/intent.py`
- Optionally modify: `skill/orchestrator/query_traits.py`

**Step 1: Add missing academic, policy, industry, and multilingual policy markers**

**Step 2: Tighten cross-domain detection for combined-route phrasing without over-triggering on generic conjunctions**

**Step 3: Keep routing deterministic and precedence-compatible**

### Task 3: Verify routing contracts and benchmark impact

**Files:**
- Test: `tests/test_intent_task2.py`
- Test: `tests/test_route_contracts.py`
- Artifact: `benchmark-results/generated-hidden-like-r1-v32-local/`

**Step 1: Run focused routing tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_intent_task2.py tests/test_route_contracts.py --import-mode=importlib`
Expected: PASS

**Step 2: Run full test suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`
Expected: PASS

**Step 3: Run a fresh benchmark**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-14.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v32-local`
Expected: compare against `v31` for net benchmark gain before retaining.
