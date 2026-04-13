# WASC Precision / Stability Edition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `WASC` into a second competition-ready submission that preserves its current speed, stability, and grounded-answer contract while materially improving Chinese and mixed-domain competition-style query handling.

**Architecture:** Keep the existing `/route` -> `/retrieve` -> `/answer` pipeline and make targeted internal upgrades instead of a rewrite. Add richer route/query traits, budgeted query variants, stronger mixed-domain evidence ordering, wider local-first answer paths, post-generation guardrails, and a quality-gated repeat-run cache.

**Tech Stack:** Python 3.12, FastAPI, existing retrieval/evidence/synthesis modules, pytest, existing benchmark harness

---

## Implementation Rules

- Use an isolated worktree before changing code if possible.
- The repo is already dirty. Stage only the files listed in each task.
- Keep API contracts unchanged unless a test explicitly requires an additive change.
- Favor TDD and the smallest change that moves the benchmark toward competition robustness.
- After each task, run only the listed focused tests before committing.

### Task 1: Add Query Traits And Expand Route Signals

**Files:**
- Create: `skill/orchestrator/query_traits.py`
- Modify: `skill/config/routes.py`
- Modify: `skill/orchestrator/intent.py`
- Modify: `tests/test_intent_task2.py`
- Modify: `tests/test_route_contracts.py`

**Step 1: Write the failing tests**

Add focused regressions for:

- Chinese policy change queries
- Chinese industry trend / shipment / forecast queries
- Chinese/English academic lookup queries
- mixed impact queries that should keep concrete primary and supplemental routes
- trait extraction for year, version/date intent, trend intent, and cross-domain impact

Example test shape:

```python
from skill.orchestrator.intent import classify_query
from skill.orchestrator.query_traits import derive_query_traits


def test_classify_query_routes_chinese_policy_change_query() -> None:
    result = classify_query("2025年个人信息出境认证办法修订了哪些条款")
    assert result.route_label == "policy"


def test_derive_query_traits_detects_year_and_policy_change() -> None:
    traits = derive_query_traits("2025年数据出境安全评估办法有哪些变化")
    assert traits.has_year is True
    assert traits.is_policy_change is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_intent_task2.py tests/test_route_contracts.py -q
```

Expected:

- FAIL because the new trait helper does not exist yet
- FAIL because current markers still classify several Chinese competition-style queries too weakly

**Step 3: Write minimal implementation**

Implement:

- `skill/orchestrator/query_traits.py`
  - define a small immutable query-traits model
  - expose `derive_query_traits(query: str) -> QueryTraits`
- `skill/config/routes.py`
  - add Chinese and bilingual markers for:
    - revision / change / exemption / effective date
    - trend / shipment / sales / market share / forecast
    - paper / review / survey / benchmark
    - impact / effect / regulation-on-industry patterns
- `skill/orchestrator/intent.py`
  - use the expanded markers
  - keep current public classification result fields stable
  - add traits to the internal result model only if it can be done without breaking callers; otherwise derive them separately in later layers

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_intent_task2.py tests/test_route_contracts.py -q
```

Expected:

- PASS
- English locked-benchmark routing tests still pass
- New Chinese/bilingual route regressions pass

**Step 5: Commit**

```bash
git add -- skill/orchestrator/query_traits.py skill/config/routes.py skill/orchestrator/intent.py tests/test_intent_task2.py tests/test_route_contracts.py
git commit -m "feat: expand route traits for competition queries"
```

### Task 2: Add Budgeted Query Variant Planning

**Files:**
- Create: `skill/retrieval/query_variants.py`
- Modify: `skill/orchestrator/retrieval_plan.py`
- Modify: `skill/retrieval/engine.py`
- Modify: `tests/test_retrieval_integration.py`
- Create: `tests/test_retrieval_query_variants.py`

**Step 1: Write the failing tests**

Add regressions that verify:

- route-aware query variants are generated only when traits justify them
- policy queries get change/version/effective-date variants
- industry queries get trend/shipment/share variants
- mixed queries split into primary and supplemental route-specific variants
- query variant count stays bounded
- duplicate variants are removed before execution

Example test shape:

```python
from skill.retrieval.query_variants import build_query_variants


def test_build_query_variants_caps_policy_expansion() -> None:
    variants = build_query_variants(
        query="2025年数据出境安全评估办法有哪些变化",
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
    )
    assert 1 <= len(variants) <= 3
    assert any("变化" in item.query for item in variants)
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_retrieval_query_variants.py tests/test_retrieval_integration.py -q
```

Expected:

- FAIL because `skill/retrieval/query_variants.py` and the new plan shape do not exist yet

**Step 3: Write minimal implementation**

Implement:

- `skill/retrieval/query_variants.py`
  - define a small query-variant model
  - implement bounded expansion and dedupe
- `skill/orchestrator/retrieval_plan.py`
  - attach query-variant information to planned source steps without changing public API output
- `skill/retrieval/engine.py`
  - run each source step against its variant list within the same source/overall deadlines
  - merge hits across variants
  - avoid blowing the concurrency cap

Keep the first pass simple:

- max 3 variants per step
- route-aware only
- no semantic expansion or external rewrite layer

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_retrieval_query_variants.py tests/test_retrieval_integration.py -q
```

Expected:

- PASS
- existing retrieval integration tests remain green

**Step 5: Commit**

```bash
git add -- skill/retrieval/query_variants.py skill/orchestrator/retrieval_plan.py skill/retrieval/engine.py tests/test_retrieval_query_variants.py tests/test_retrieval_integration.py
git commit -m "feat: add budgeted retrieval query variants"
```

### Task 3: Improve Retrieval Priority And Mixed-Domain Coverage

**Files:**
- Modify: `skill/retrieval/priority.py`
- Modify: `skill/retrieval/orchestrate.py`
- Modify: `tests/test_retrieval_integration.py`
- Create: `tests/test_mixed_coverage_priority.py`

**Step 1: Write the failing tests**

Add regressions that verify:

- query entity/year overlap improves ranking
- change/impact/trend wording affects ordering
- mixed queries retain at least one usable primary and one usable supplemental evidence record when both exist
- same-domain crowding does not suppress supplemental evidence in the final retained set

Example test shape:

```python
def test_mixed_evidence_pack_keeps_both_routes_when_both_have_usable_hits() -> None:
    response = ...
    assert any(item.route_role == "primary" for item in response.canonical_evidence)
    assert any(item.route_role == "supplemental" for item in response.canonical_evidence)
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mixed_coverage_priority.py tests/test_retrieval_integration.py -q
```

Expected:

- FAIL because current ordering is still too generic and mixed retention is not strong enough

**Step 3: Write minimal implementation**

Implement:

- stronger normalized query-match scoring in `skill/retrieval/priority.py`
- route-sensitive weighting for:
  - years
  - version/effective-date terms
  - change/impact/trend phrases
- `skill/retrieval/orchestrate.py`
  - preserve mixed coverage when both routes have credible evidence
  - keep current domain-first ordering philosophy

Do not:

- add a new reranker model
- add heavy fuzzy matching
- make supplemental evidence outrank stronger primary evidence by default

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_mixed_coverage_priority.py tests/test_retrieval_integration.py -q
```

Expected:

- PASS
- existing policy/academic/industry retrieval regressions still pass

**Step 5: Commit**

```bash
git add -- skill/retrieval/priority.py skill/retrieval/orchestrate.py tests/test_mixed_coverage_priority.py tests/test_retrieval_integration.py
git commit -m "feat: strengthen mixed evidence prioritization"
```

### Task 4: Widen Local Fast Paths And Add Post-Generation Guardrails

**Files:**
- Modify: `skill/synthesis/orchestrate.py`
- Modify: `skill/synthesis/prompt.py`
- Modify: `tests/test_answer_integration.py`
- Modify: `tests/test_answer_runtime_budget.py`
- Create: `tests/test_answer_guardrails.py`

**Step 1: Write the failing tests**

Add regressions for:

- Chinese policy change/version/effective-date queries using local fast paths when evidence is sufficient
- mixed impact queries preferring local structured answers when both route slices are strong
- model output falling back when it:
  - drops a year/version/effective date
  - drops a core entity
  - weakens mixed cross-domain coverage
  - cites weaker/no sources than the local candidate

Example test shape:

```python
def test_answer_pipeline_falls_back_to_local_candidate_when_model_drops_effective_date() -> None:
    result = ...
    assert result.response.answer_status == "grounded_success"
    assert "2026-04-01" in result.response.conclusion
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_answer_integration.py tests/test_answer_runtime_budget.py tests/test_answer_guardrails.py -q
```

Expected:

- FAIL because current orchestration does not compare the generated answer against a stronger local candidate

**Step 3: Write minimal implementation**

Implement in `skill/synthesis/orchestrate.py`:

- a wider local candidate builder for:
  - policy version/date/change lookups
  - industry trend/share/forecast lookups
  - mixed cross-domain impact queries
- post-generation comparison logic against the local candidate
- conservative fallback rules when generation weakens grounded output

Implement in `skill/synthesis/prompt.py`:

- tighten prompt instructions so the model preserves:
  - core entities
  - years / versions / effective dates
  - route coverage for mixed queries

Do not:

- loosen citation validation
- let the model bypass evidence-backed constraints

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_answer_integration.py tests/test_answer_runtime_budget.py tests/test_answer_guardrails.py -q
```

Expected:

- PASS
- existing fast-path and budget tests remain green

**Step 5: Commit**

```bash
git add -- skill/synthesis/orchestrate.py skill/synthesis/prompt.py tests/test_answer_integration.py tests/test_answer_runtime_budget.py tests/test_answer_guardrails.py
git commit -m "feat: add guarded local-first answer fallbacks"
```

### Task 5: Add Stable Grounded-Response Cache

**Files:**
- Create: `skill/synthesis/cache.py`
- Modify: `skill/synthesis/orchestrate.py`
- Modify: `tests/test_answer_runtime_budget.py`
- Modify: `tests/test_api_runtime_benchmark.py`
- Create: `tests/test_answer_cache.py`

**Step 1: Write the failing tests**

Add regressions that verify:

- identical normalized queries can reuse a cached grounded response
- only grounded stable responses are cached
- insufficient-evidence and retrieval-failure responses are not cached
- cache keys include a pipeline version string so future changes do not cross-contaminate runs
- public API payloads still do not expose internal cache/runtime fields

Example test shape:

```python
def test_answer_cache_only_stores_grounded_success() -> None:
    cache = ...
    assert cache.get("weak-query") is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_answer_cache.py tests/test_answer_runtime_budget.py tests/test_api_runtime_benchmark.py -q
```

Expected:

- FAIL because no cache exists yet

**Step 3: Write minimal implementation**

Implement:

- `skill/synthesis/cache.py`
  - in-process cache object
  - normalized key builder
  - versioned key support
- `skill/synthesis/orchestrate.py`
  - read cache before retrieval/generation where safe
  - write cache only for validated stable grounded responses

Keep it simple:

- no persistent disk cache
- no TTL on first pass
- no cache for weak states

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_answer_cache.py tests/test_answer_runtime_budget.py tests/test_api_runtime_benchmark.py -q
```

Expected:

- PASS
- runtime telemetry remains internal
- repeated benchmark-path behavior stays deterministic

**Step 5: Commit**

```bash
git add -- skill/synthesis/cache.py skill/synthesis/orchestrate.py tests/test_answer_cache.py tests/test_answer_runtime_budget.py tests/test_api_runtime_benchmark.py
git commit -m "feat: cache stable grounded answers for repeated runs"
```

### Task 6: Run Locked-Benchmark And Full Regression Verification

**Files:**
- Modify if needed: `README.md`
- Modify if needed: `benchmark-results/benchmark-summary.json`
- Modify if needed: `benchmark-results/benchmark-runs.csv`
- Modify if needed: `benchmark-results/benchmark-runs.jsonl`

**Step 1: Run focused test groups**

Run:

```bash
pytest tests/test_intent_task2.py tests/test_route_contracts.py tests/test_retrieval_integration.py tests/test_answer_integration.py tests/test_answer_runtime_budget.py tests/test_api_runtime_benchmark.py -q
```

Expected:

- PASS

**Step 2: Run the full suite**

Run:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

Expected:

- PASS for the full repository test suite

**Step 3: Run the locked benchmark**

Run:

```bash
python scripts/run_benchmark.py --cases tests/fixtures/benchmark_phase5_cases.json --runs 5 --output-dir benchmark-results
```

Expected:

- benchmark artifacts refresh successfully
- no regression in repeatability
- latency and token budget pass rates remain strong

**Step 4: Run the competition-style regression**

Run:

```bash
python scripts/run_wasc_on_wasc1_eval.py
```

Expected:

- the report still completes successfully
- intent accuracy, source counts, and keyword coverage improve materially from the previous baseline
- do not require parity with `WASC1`; require clear movement away from near-zero behavior

**Step 5: Commit**

If code needed no further fixes after verification:

```bash
git add -- README.md benchmark-results/benchmark-summary.json benchmark-results/benchmark-runs.csv benchmark-results/benchmark-runs.jsonl benchmark-results/wasc-on-wasc1-eval-report.json
git commit -m "test: verify precision stability competition upgrade"
```

If no docs or artifact refresh should be committed, skip the commit and capture the verification output in the implementation summary instead.

### Task 7: Refresh Submission Messaging If Behavior Changed

**Files:**
- Modify: `README.md`
- Modify if needed: `SETUP.md`
- Modify if needed: `SKILL.md`

**Step 1: Write the failing documentation expectation**

Create a short checklist in the task notes for:

- positioning this repo as the precision/stability submission
- documenting the new guarded local-first behavior
- documenting competition-style robustness improvements without overselling parity with `WASC1`

**Step 2: Run a quick diff review**

Run:

```bash
git diff -- README.md SETUP.md SKILL.md
```

Expected:

- either no changes are needed
- or the current docs under-describe the new competition positioning

**Step 3: Write minimal documentation updates**

Update docs only if implementation materially changed externally visible behavior.

Document:

- precision/stability positioning
- route-aware bounded expansion
- local-first grounded answer behavior
- repeat-run cache only if it affects expectations

**Step 4: Re-run targeted doc-adjacent smoke checks**

Run:

```bash
pytest tests/test_api_answer_endpoint.py tests/test_api_runtime_benchmark.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add -- README.md SETUP.md SKILL.md
git commit -m "docs: refresh precision stability submission messaging"
```

