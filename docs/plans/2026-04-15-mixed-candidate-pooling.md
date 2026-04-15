# Mixed Candidate Pooling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a mixed-only shallow-first candidate pooling path that discovers cheap policy and supplemental candidates first, then spends deep-fetch budget only on a small cross-domain shortlist.

**Architecture:** Extend the retrieval plan with mixed-specific discovery and deep-enrichment budgets, split `policy_official_registry` and `industry_ddgs` into cheap discovery plus shortlist-only enrichment helpers, and orchestrate them from `engine.py`. Preserve the current non-mixed retrieval path and fall back to it when pooled mixed discovery cannot form a viable dual-route shortlist.

**Tech Stack:** Python, pytest, FastAPI, existing retrieval adapters and evidence pipeline

---

### Task 1: Add failing tests for mixed pooled discovery behavior

**Files:**
- Create: `tests/test_mixed_candidate_pooling.py`
- Modify: `tests/test_retrieval_query_variants.py`

**Step 1: Write the failing test**

```python
def test_mixed_pooled_retrieval_builds_dual_route_shortlist_before_deep_fetch() -> None:
    ...
```

The test should prove:

- mixed retrieval uses a shallow discovery phase first
- both primary and supplemental discovery candidates enter the shortlist
- deep enrichment only runs for shortlist items

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py::test_mixed_pooled_retrieval_builds_dual_route_shortlist_before_deep_fetch --import-mode=importlib`

Expected: FAIL because the mixed pooled path does not exist yet.

**Step 3: Write a second failing test**

```python
def test_mixed_pooled_retrieval_keeps_shallow_hits_when_deep_enrichment_times_out() -> None:
    ...
```

The test should prove shallow candidates are retained when deep stage fails.

**Step 4: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py::test_mixed_pooled_retrieval_keeps_shallow_hits_when_deep_enrichment_times_out --import-mode=importlib`

Expected: FAIL because deep fallback preservation is not implemented yet.

**Step 5: Commit**

```bash
git add tests/test_mixed_candidate_pooling.py tests/test_retrieval_query_variants.py
git commit -m "test: add failing mixed candidate pooling regressions"
```

### Task 2: Add mixed-specific budget fields to retrieval planning

**Files:**
- Modify: `skill/orchestrator/retrieval_plan.py`
- Modify: `tests/test_retrieval_query_variants.py`

**Step 1: Write the failing test**

```python
def test_build_retrieval_plan_partitions_mixed_budget_for_discovery_and_deep_fetch() -> None:
    plan = build_retrieval_plan(...)
    assert plan.overall_deadline_seconds == 8.0
    assert plan.mixed_discovery_deadline_seconds == 2.5
    assert plan.mixed_deep_deadline_seconds == 5.0
    assert plan.mixed_shortlist_top_k == 4
```

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_query_variants.py::test_build_retrieval_plan_partitions_mixed_budget_for_discovery_and_deep_fetch --import-mode=importlib`

Expected: FAIL because `RetrievalPlan` does not expose these mixed fields yet.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class RetrievalPlan:
    ...
    mixed_discovery_deadline_seconds: float | None = None
    mixed_deep_deadline_seconds: float | None = None
    mixed_shortlist_top_k: int = 0
```

Populate those values only for mixed plans.

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_retrieval_query_variants.py::test_build_retrieval_plan_partitions_mixed_budget_for_discovery_and_deep_fetch --import-mode=importlib`

Expected: PASS

**Step 5: Commit**

```bash
git add skill/orchestrator/retrieval_plan.py tests/test_retrieval_query_variants.py
git commit -m "feat: add mixed pooled retrieval budgets"
```

### Task 3: Introduce shallow discovery models and engine orchestration

**Files:**
- Create: `skill/retrieval/discovery.py`
- Modify: `skill/retrieval/engine.py`
- Test: `tests/test_mixed_candidate_pooling.py`

**Step 1: Write the failing test**

```python
def test_mixed_pooled_retrieval_shortlists_top_cross_domain_candidates() -> None:
    ...
```

The test should cover:

- shallow discovery candidates are merged across variants
- provenance is preserved on candidates
- shortlist keeps at least one primary and one supplemental candidate

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py::test_mixed_pooled_retrieval_shortlists_top_cross_domain_candidates --import-mode=importlib`

Expected: FAIL because no mixed pooled engine path exists.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class DiscoveryCandidate:
    source_id: str
    target_route: str
    title: str
    url: str
    snippet: str
    credibility_tier: str | None
    variant_reason_codes: tuple[str, ...]
    variant_queries: tuple[str, ...]
    candidate_score: float
    needs_deep_fetch: bool = True
```

In `engine.py`, add helpers shaped roughly like:

```python
async def _run_mixed_pooled_retrieval(...): ...
def _shortlist_mixed_candidates(...): ...
def _candidate_to_retrieval_hit(...): ...
```

Rules:

- use pooled path only for mixed plans with both routes present
- build route-local shortlist using provenance-aware fragment alignment
- if no viable dual-route shortlist exists, fall back to current mixed path with remaining time

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py::test_mixed_pooled_retrieval_shortlists_top_cross_domain_candidates --import-mode=importlib`

Expected: PASS

**Step 5: Commit**

```bash
git add skill/retrieval/discovery.py skill/retrieval/engine.py tests/test_mixed_candidate_pooling.py
git commit -m "feat: add mixed pooled retrieval orchestration"
```

### Task 4: Split policy adapter into cheap discovery and shortlist-only enrichment

**Files:**
- Modify: `skill/retrieval/adapters/policy_official_registry.py`
- Modify: `tests/test_policy_live_adapters.py`
- Test: `tests/test_mixed_candidate_pooling.py`

**Step 1: Write the failing test**

```python
def test_policy_discovery_candidates_skip_page_fetch_until_deep_stage(monkeypatch) -> None:
    ...
```

The test should prove `discover_candidates()` does not call `fetch_page_text()`.

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_policy_live_adapters.py::test_policy_discovery_candidates_skip_page_fetch_until_deep_stage --import-mode=importlib`

Expected: FAIL because policy discovery/deep split does not exist yet.

**Step 3: Write minimal implementation**

Add helpers like:

```python
async def discover_candidates(query: str, *, max_results: int) -> list[DiscoveryCandidate]:
    ...

async def enrich_candidates(
    query: str,
    *,
    candidates: list[DiscoveryCandidate],
    config: LiveRetrievalConfig,
) -> list[RetrievalHit]:
    ...
```

Discovery should reuse direct-source and structured-record ranking, but stop before page fetch.

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_policy_live_adapters.py::test_policy_discovery_candidates_skip_page_fetch_until_deep_stage --import-mode=importlib`

Expected: PASS

**Step 5: Commit**

```bash
git add skill/retrieval/adapters/policy_official_registry.py tests/test_policy_live_adapters.py tests/test_mixed_candidate_pooling.py
git commit -m "feat: split policy mixed discovery from deep enrichment"
```

### Task 5: Split industry adapter into cheap discovery and shortlist-only enrichment

**Files:**
- Modify: `skill/retrieval/adapters/industry_ddgs.py`
- Modify: `tests/test_industry_live_adapter.py`
- Test: `tests/test_mixed_candidate_pooling.py`

**Step 1: Write the failing test**

```python
def test_industry_discovery_candidates_skip_query_aligned_fetch_until_deep_stage(monkeypatch) -> None:
    ...
```

The test should prove `discover_candidates()` does not call:

- `fetch_page_text`
- `_fetch_query_aligned_page_text`

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_industry_live_adapter.py::test_industry_discovery_candidates_skip_query_aligned_fetch_until_deep_stage --import-mode=importlib`

Expected: FAIL because industry discovery/deep split does not exist yet.

**Step 3: Write minimal implementation**

Discovery should keep:

- direct official candidates
- SEC / company-submission record discovery
- SERP discovery and lightweight ranking

Deep stage should apply current expensive enrichment only to shortlist candidates.

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_industry_live_adapter.py::test_industry_discovery_candidates_skip_query_aligned_fetch_until_deep_stage --import-mode=importlib`

Expected: PASS

**Step 5: Commit**

```bash
git add skill/retrieval/adapters/industry_ddgs.py tests/test_industry_live_adapter.py tests/test_mixed_candidate_pooling.py
git commit -m "feat: split industry mixed discovery from deep enrichment"
```

### Task 6: Add end-to-end mixed integration and fallback coverage

**Files:**
- Modify: `tests/test_retrieval_integration.py`
- Modify: `tests/test_mixed_candidate_pooling.py`
- Modify: `skill/retrieval/engine.py`

**Step 1: Write the failing test**

```python
def test_mixed_pooled_retrieval_falls_back_to_standard_path_when_dual_route_shortlist_missing() -> None:
    ...
```

Add another integration test proving:

- pooled path wins when both routes produce candidates
- standard path is reused when discovery cannot form a dual-route shortlist

**Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py tests/test_retrieval_integration.py --import-mode=importlib`

Expected: FAIL until fallback behavior is implemented correctly.

**Step 3: Write minimal implementation**

In `engine.py`:

```python
if pooled_result_is_usable:
    return pooled_result
return await _run_standard_retrieval_with_remaining_time(...)
```

**Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py tests/test_retrieval_integration.py --import-mode=importlib`

Expected: PASS

**Step 5: Commit**

```bash
git add skill/retrieval/engine.py tests/test_mixed_candidate_pooling.py tests/test_retrieval_integration.py
git commit -m "feat: add mixed pooled retrieval fallback behavior"
```

### Task 7: Run regression suite and benchmark gates

**Files:**
- Modify: `HANDOFF.md`
- Artifact: `benchmark-results/generated-hidden-like-r1-v44-*/`

**Step 1: Run focused tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_mixed_candidate_pooling.py tests/test_policy_live_adapters.py tests/test_industry_live_adapter.py tests/test_retrieval_integration.py --import-mode=importlib`

Expected: PASS

**Step 2: Run full suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`

Expected: PASS

**Step 3: Run local guardrail**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-14.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v44-local`

Expected: no material regression versus v43 local.

**Step 4: Run fresh holdout 1**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v44-generalization`

Expected: `mixed` improves above `0 / 10`.

**Step 5: Run fresh holdout 2**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization_round2.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v44-generalization-round2`

Expected: timeout-heavy mixed failures decrease.

**Step 6: Update handoff**

Document:

- tests run
- benchmark deltas
- remaining timeout failure shapes
- next recommended move

**Step 7: Commit**

```bash
git add HANDOFF.md benchmark-results/generated-hidden-like-r1-v44-local benchmark-results/generated-hidden-like-r1-v44-generalization benchmark-results/generated-hidden-like-r1-v44-generalization-round2
git commit -m "docs: record mixed candidate pooling results"
```
