# Academic Retrieval Uplift Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce academic retrieval misses by tightening fixture shortcuts, adding condensed academic query variants, and promoting more query-aligned academic evidence to the local grounded-answer fast path.

**Architecture:** Keep the existing browser-free route -> retrieve -> answer flow. Improve academic behavior in three bounded places only: route-aware query shaping, academic adapter shortcut admission, and academic local fast-path gating. Do not add new services or expand the public API.

**Tech Stack:** Python, FastAPI, pytest, async retrieval adapters, existing evidence/synthesis pipeline

---

### Task 1: Add failing academic query-variant regressions

**Files:**
- Modify: `tests/test_retrieval_query_variants.py`
- Modify: `skill/retrieval/query_variants.py`

**Step 1: Write the failing test**

Add tests showing that long academic queries now need:

- the original query preserved
- one condensed topic-focused academic variant
- optional source-hinted variant when the query explicitly mentions repositories like `arXiv` or `Europe PMC`

Use benchmark-like queries that currently only grow longer with `paper research` or `survey benchmark`.

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py --import-mode=importlib
```

Expected:

- FAIL because academic variants currently only append broad lookup words.

**Step 3: Write minimal implementation**

Implement bounded academic condensation helpers in `skill/retrieval/query_variants.py`.

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 2: Add failing academic shortcut-admission regressions

**Files:**
- Modify: `tests/test_academic_live_adapters.py`
- Modify: `skill/retrieval/adapters/academic_asta_mcp.py`
- Modify: `skill/retrieval/adapters/academic_semantic_scholar.py`
- Modify: `skill/retrieval/adapters/academic_arxiv.py`
- Modify: `skill/retrieval/adapters/academic_live_common.py`

**Step 1: Write the failing test**

Add tests proving that:

- generic academic wording alone must not unlock deterministic fixture shortcuts
- shortcut admission should require stronger topic overlap than broad words like `retrieval`, `evaluation`, or `benchmark`
- genuinely aligned known-topic academic lookups can still use shortcut results

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_academic_live_adapters.py --import-mode=importlib
```

Expected:

- FAIL because current academic shortcuts admit overly generic matches.

**Step 3: Write minimal implementation**

Add a shared academic shortcut-admission helper and use it across the three academic adapters.

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 3: Add failing academic local-fast-path regressions

**Files:**
- Modify: `tests/test_answer_runtime_budget.py`
- Modify: `skill/synthesis/orchestrate.py`

**Step 1: Write the failing test**

Add a regression showing that when academic retrieval returns clipped but clearly query-aligned retained slices, the answer path should produce a local grounded response instead of exhausting synthesis budget.

The test should use synthetic canonical evidence, not a live network dependency.

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_answer_runtime_budget.py --import-mode=importlib
```

Expected:

- FAIL because the current academic fast-path gate is too strict.

**Step 3: Write minimal implementation**

Relax the academic fast-path admission logic only enough to accept strongly aligned clipped evidence.

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 4: Run focused verification

**Files:**
- Modify: none

**Step 1: Run focused suites**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests/test_retrieval_query_variants.py tests/test_academic_live_adapters.py tests/test_answer_runtime_budget.py --import-mode=importlib
```

Expected:

- PASS

**Step 2: Run the full suite**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q tests --import-mode=importlib
```

Expected:

- PASS

**Step 3: Run one hidden-like benchmark comparison**

Run:

```powershell
python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-14.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v16-local
```

Expected:

- benchmark completes
- academic coverage should improve relative to `generated-hidden-like-r1-v15-local`

**Step 4: Commit**

Do not commit yet.
