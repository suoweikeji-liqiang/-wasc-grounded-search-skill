# Academic Search Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a bounded academic search-optimization layer that generates more orthogonal academic query variants and prioritizes them during retrieval execution without increasing the default runtime variant budget.

**Architecture:** Keep the existing route -> retrieval-plan -> retrieval-engine flow. Implement the new behavior entirely in query-variant generation, academic execution ordering, and the academic route's variant budget.

**Tech Stack:** Python, pytest, async retrieval engine

---

### Task 1: Add failing academic search-portfolio tests

**Files:**
- Modify: `tests/test_retrieval_query_variants.py`

**Step 1: Write the failing test**

Add tests proving that academic queries can now generate:

- a source-hinted condensed variant for explicit repository hints
- a phrase-locked condensed variant for strong technical noun phrases
- an evidence-type-focused variant when the query already carries evidence-type language

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib
```

Expected:

- FAIL because the current query planner does not build the new portfolio yet

**Step 3: Commit**

Do not commit yet.

### Task 2: Add failing academic execution-priority tests

**Files:**
- Modify: `tests/test_retrieval_query_variants.py`
- Modify: `skill/orchestrator/retrieval_plan.py`

**Step 1: Write the failing test**

Add regressions proving that:

- phrase-locked academic variants can exist for strong technical phrase queries
- under a tight timeout, academic retrieval tries the optimized portfolio before falling back to the raw original query

**Step 2: Run test to verify it fails**

Run the same focused query-variant test command.

Expected:

- FAIL because academic execution ordering still uses the older variant ordering

**Step 3: Commit**

Do not commit yet.

### Task 3: Implement the academic search-optimization layer

**Files:**
- Modify: `skill/retrieval/query_variants.py`
- Modify: `skill/retrieval/engine.py`
- Modify: `skill/orchestrator/retrieval_plan.py`

**Step 1: Write minimal implementation**

Implement:

- new academic portfolio helpers for source-hint, phrase-locked, and evidence-type-focused variants
- academic execution priority that prefers the optimized portfolio before the raw original query

Retained scope note:

- do not keep a runtime budget increase if benchmark evidence shows regression

**Step 2: Run focused tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib
```

Expected:

- PASS

**Step 3: Commit**

Do not commit yet.

### Task 4: Run verification

**Files:**
- Modify: none

**Step 1: Run focused verification**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib
```

Expected:

- PASS

**Step 2: Run broader verification if focused tests are stable**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py tests/test_academic_live_adapters.py tests/test_answer_runtime_budget.py --import-mode=importlib
```

Expected:

- PASS

**Step 3: Commit**

Do not commit yet.
