# Academic Quality-Gated Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow primary academic retrieval to continue into scholarly fallback when the first source returns non-empty but weak/off-center evidence.

**Architecture:** Keep the existing staged academic retrieval shape and add a narrow acceptance gate in the runtime engine instead of adding more literal routing heuristics. The gate should only affect primary academic retrieval, preserve already-returned hits, and trigger fallback when the first successful source does not meet a minimum topical-specificity bar.

**Tech Stack:** Python, pytest, asyncio

---

### Task 1: Add the failing retrieval regression

**Files:**
- Modify: `tests/test_retrieval_fallback.py`
- Reference: `skill/retrieval/engine.py`

**Step 1: Write the failing test**

```python
def test_run_retrieval_primary_academic_weak_semantic_scholar_success_still_runs_fallback() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py::test_run_retrieval_primary_academic_weak_semantic_scholar_success_still_runs_fallback --import-mode=importlib`
Expected: FAIL because the current engine accepts the weak `academic_semantic_scholar` hit and never calls `academic_arxiv`.

**Step 3: Keep the test focused**

```python
# Assert the weak semantic-scholar hit is retained but arXiv still runs afterward.
```

**Step 4: Re-run the same test**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py::test_run_retrieval_primary_academic_weak_semantic_scholar_success_still_runs_fallback --import-mode=importlib`
Expected: still FAIL until production code changes.

### Task 2: Add the minimal runtime quality gate

**Files:**
- Modify: `skill/retrieval/engine.py`
- Reference: `skill/retrieval/priority.py`

**Step 1: Add a narrow academic acceptance helper**

```python
def _academic_success_requires_fallback(...) -> bool:
    ...
```

**Step 2: Wire the helper into `run_retrieval()`**

```python
if primary_result.status == "success" and _academic_success_requires_fallback(...):
    ...
```

**Step 3: Preserve already-returned weak hits**

```python
provisional_hits = list(primary_result.hits)
```

**Step 4: Only apply the gate to the primary academic staged path**

```python
if plan.route_label != "academic" or step.source.source_id != "academic_semantic_scholar":
    return False
```

**Step 5: Re-run the focused regression**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_fallback.py::test_run_retrieval_primary_academic_weak_semantic_scholar_success_still_runs_fallback --import-mode=importlib`
Expected: PASS

### Task 3: Verify no staged academic contract regressed

**Files:**
- Test: `tests/test_retrieval_concurrency.py`
- Test: `tests/test_retrieval_fallback.py`

**Step 1: Run the targeted retrieval runtime tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_concurrency.py tests/test_retrieval_fallback.py --import-mode=importlib`
Expected: PASS

**Step 2: Run the full test suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`
Expected: PASS

**Step 3: Update handoff notes if the change is retained**

```markdown
- added academic quality-gated fallback so weak semantic-scholar hits do not terminate staged retrieval early
```
