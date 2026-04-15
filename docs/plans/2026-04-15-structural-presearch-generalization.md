# Structural Presearch Generalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve generalization by broadening retrieval presearch structurally instead of adding more sample-specific keyword and regex patches.

**Architecture:** Keep the current route classifier intact, but expand retrieval-time query generation with route-agnostic structural variants. Add generic cross-domain fragment variants for `mixed`-shaped queries, generic filing/report focus variants for document lookups, and wider variant budgets for `mixed` and primary `industry` retrieval so adapters see a broader evidence surface before failing.

**Tech Stack:** Python, pytest, FastAPI, existing retrieval engine/query variant pipeline

---

### Task 1: Add failing regression tests for structural presearch behavior

**Files:**
- Modify: `tests/test_retrieval_query_variants.py`

**Step 1: Write failing tests for mixed cross-domain fragment variants**

**Step 2: Write failing tests for industry filing/report structural variants**

**Step 3: Write failing tests for wider mixed/industry variant budgets**

**Step 4: Run focused tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib`
Expected: FAIL on the new structural-variant assertions.

### Task 2: Implement route-agnostic structural query decomposition

**Files:**
- Modify: `skill/retrieval/query_variants.py`

**Step 1: Add generic core-query compaction that removes low-information wrapper terms without route-specific sample hacks**

**Step 2: Add generic cross-domain fragment extraction around broad connectors and rank fragments by route compatibility**

**Step 3: Add generic filing/report focus variants for company/document queries**

**Step 4: Keep existing route-specific variants as fallback rather than primary mechanism**

### Task 3: Widen presearch budgets where generalization needs it

**Files:**
- Modify: `skill/orchestrator/retrieval_plan.py`
- Modify: `tests/test_retrieval_query_variants.py`

**Step 1: Increase `query_variant_budget` for primary `industry` retrieval**

**Step 2: Increase `query_variant_budget` for `mixed` retrieval**

**Step 3: Verify unchanged concrete-route timing contracts still hold where expected**

### Task 4: Verify end-to-end impact

**Files:**
- Test: `tests/test_retrieval_query_variants.py`
- Artifact: `benchmark-results/generated-hidden-like-r1-v42-generalization/`

**Step 1: Run focused tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib`
Expected: PASS

**Step 2: Run full suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`
Expected: PASS

**Step 3: Run fresh generalization benchmark**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization_round2.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v42-generalization`
Expected: improvement comes from broader retrieval evidence, not extra sample-specific marker patches.
