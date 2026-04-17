# Academic Fallback Narrowing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Shorten academic retrieval source execution paths so live hidden-style runs prioritize success rate and deadline discipline over long-tail discovery recall.

**Architecture:** Keep academic source-to-source fallback in the retrieval engine, but narrow the academic metadata adapters so they stop after structured metadata sources instead of hiding slow web discovery inside a single source budget. Preserve the existing staged fallback shape (`semantic_scholar -> arxiv -> asta`) and the new engine-level academic upstream-query dedupe.

**Tech Stack:** Python 3.12, pytest, asyncio, existing academic live adapters and retrieval engine.

---

### Task 1: Lock adapter-boundary behavior with failing tests

**Files:**
- Modify: `tests/test_academic_live_adapters.py`
- Reference: `skill/retrieval/adapters/academic_semantic_scholar.py`
- Reference: `skill/retrieval/adapters/academic_arxiv.py`

**Step 1: Write the failing Semantic Scholar test**

Add a test proving `academic_semantic_scholar.search_live()` does not call `search_multi_engine` after both Semantic Scholar and OpenAlex fail or return empty results.

```python
async def _empty_semantic_scholar(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
    return []

async def _empty_openalex(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
    return []

async def _unexpected_search_multi_engine(**_: object):
    raise AssertionError("search_multi_engine should not be called")
```

Expected assertion:

```python
hits = asyncio.run(adapter.search_live("evidence ranking benchmark"))
assert hits == []
```

**Step 2: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_academic_live_adapters.py -k semantic_scholar_live_adapter_does_not_fallback_to_search_discovery --import-mode=importlib`

Expected: FAIL because the adapter still calls `search_multi_engine`.

**Step 3: Write the failing arXiv test**

Add a test proving `academic_arxiv.search_live()` does not call `search_multi_engine` after both arXiv and Europe PMC fail or return empty results.

```python
async def _empty_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
    return []

async def _empty_europe_pmc(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
    return []

async def _unexpected_search_multi_engine(**_: object):
    raise AssertionError("search_multi_engine should not be called")
```

Expected assertion:

```python
hits = asyncio.run(adapter.search_live("evidence ranking benchmark"))
assert hits == []
```

**Step 4: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_academic_live_adapters.py -k arxiv_live_adapter_does_not_fallback_to_search_discovery --import-mode=importlib`

Expected: FAIL because the adapter still calls `search_multi_engine`.

**Step 5: Commit**

Do not commit yet. Wait until implementation and verification pass.

---

### Task 2: Remove Semantic Scholar discovery fallback

**Files:**
- Modify: `skill/retrieval/adapters/academic_semantic_scholar.py`
- Test: `tests/test_academic_live_adapters.py`

**Step 1: Write minimal implementation**

Remove the trailing `search_multi_engine(... site:doi.org)` fallback block from `search_live()`.

The function should end after the OpenAlex path:

```python
    if openalex_hits:
        return openalex_hits

    return []
```

Also remove any now-unused imports introduced only for the deleted fallback path.

**Step 2: Run targeted tests**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_academic_live_adapters.py -k semantic_scholar_live_adapter --import-mode=importlib`

Expected: PASS for the new no-discovery test and existing Semantic Scholar adapter tests.

**Step 3: Verify no accidental contract drift**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py tests/test_retrieval_concurrency.py -k academic --import-mode=importlib`

Expected: PASS; engine-level staged fallback still works.

**Step 4: Commit**

```bash
git add tests/test_academic_live_adapters.py skill/retrieval/adapters/academic_semantic_scholar.py
git commit -m "fix: narrow semantic scholar fallback chain"
```

---

### Task 3: Remove arXiv discovery fallback

**Files:**
- Modify: `skill/retrieval/adapters/academic_arxiv.py`
- Test: `tests/test_academic_live_adapters.py`

**Step 1: Write minimal implementation**

Remove the trailing `search_multi_engine(... site:arxiv.org)` fallback block from `search_live()`.

The function should end after the Europe PMC path:

```python
    if europe_pmc_hits:
        return europe_pmc_hits

    return []
```

Also remove imports that only supported the deleted fallback path.

**Step 2: Run targeted tests**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_academic_live_adapters.py -k arxiv_live_adapter --import-mode=importlib`

Expected: PASS for the new no-discovery test and existing arXiv adapter tests.

**Step 3: Verify no accidental contract drift**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py tests/test_retrieval_concurrency.py -k academic --import-mode=importlib`

Expected: PASS; engine-level staged fallback still works.

**Step 4: Commit**

```bash
git add tests/test_academic_live_adapters.py skill/retrieval/adapters/academic_arxiv.py
git commit -m "fix: narrow arxiv fallback chain"
```

---

### Task 4: Re-verify engine-level academic dedupe and route contracts

**Files:**
- Reference: `skill/retrieval/engine.py`
- Reference: `tests/test_retrieval_query_variants.py`
- Test: `tests/test_retrieval_fallback.py`
- Test: `tests/test_retrieval_concurrency.py`

**Step 1: Run the academic upstream-query dedupe regression**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_query_variants.py -k duplicate_academic_upstream --import-mode=importlib`

Expected: PASS

**Step 2: Run academic retrieval fallback/concurrency regressions**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py tests/test_retrieval_concurrency.py --import-mode=importlib`

Expected: PASS

**Step 3: Commit**

If no new code changes were needed here, do not create an extra commit.

---

### Task 5: Run a fresh-process smoke gate and inspect traces

**Files:**
- Reference: `scripts/run_benchmark.py`
- Inspect: `benchmark-results/smoke-gate-YYYY-MM-DD-roundNN/benchmark-summary.json`
- Inspect: `benchmark-results/smoke-gate-YYYY-MM-DD-roundNN/benchmark-runs.jsonl`

**Step 1: Generate a unique cold cache directory**

Run:
`python -c "import uuid; print('.wasc-live-cache-smoke-' + uuid.uuid4().hex[:12])"`

**Step 2: Run fresh-process smoke gate**

Run:
`export WASC_RETRIEVAL_MODE=live && export WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED=0 && export WASC_LIVE_CACHE_DIR=<generated-dir> && python scripts/run_benchmark.py --smoke-gate --output-dir benchmark-results/smoke-gate-2026-04-16-roundNN`

Expected: command completes and writes `benchmark-summary.json` and `benchmark-runs.jsonl`.

**Step 3: Inspect the smoke artifact**

Check:
- overall `success_rate`
- `smoke-academic-01`
- `smoke-academic-02`
- `smoke-mixed-02`
- whether academic traces now stop at structured metadata sources without hidden discovery tail work

**Step 4: Summarize result honestly**

If success improves or traces become materially shorter/more interpretable, record that. If recall drops without enough latency/success benefit, say so explicitly.

**Step 5: Commit**

Do not commit benchmark artifacts. Only commit code/tests if additional code changes were required.
