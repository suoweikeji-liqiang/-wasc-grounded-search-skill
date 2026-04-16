# Coverage-First Retrieval Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a bounded coverage-first retrieval policy that builds a small supplemental evidence frontier after strong primary retrieval and then decides whether to stop, deepen one branch, or return insufficient evidence.

**Architecture:** Keep the current primary retrieval planner stable. Add a new policy layer between local fast-path evaluation and full grounded synthesis. That policy layer will build a tiny coverage frontier only when primary evidence is strong but incomplete, then use deterministic sufficiency checks to choose between grounded stop, one-branch deepen, or insufficient stop. The initial rollout should be generic in shape but limited in activation scope to the `policy <-> industry` complement pair.

**Tech Stack:** Python 3.12, pytest, asyncio, existing retrieval orchestration, synthesis runtime traces, live benchmark harness.

---

### Task 1: Lock the new policy behavior with failing tests

**Files:**
- Modify: `tests/test_answer_runtime_budget.py`
- Reference: `skill/synthesis/orchestrate.py`
- Create later: `skill/synthesis/retrieval_policy.py`

**Step 1: Write the failing frontier-build test**

Add a regression proving that when:

- primary `policy` retrieval succeeds
- the local fast path still cannot ground the answer
- enough budget remains

the answer pipeline builds a bounded supplemental frontier instead of immediately returning `insufficient_evidence`.

The test should monkeypatch:

- `execute_retrieval_pipeline(...)` to return strong primary policy evidence
- a fake supplemental adapter to return one aligned industry hit
- a model client that raises if grounded synthesis is called too early

Expected assertion:

```python
assert result.response.answer_status == "grounded_success"
assert any(
    entry["stage"] == "coverage_frontier_probe"
    for entry in result.runtime_trace.retrieval_trace
)
```

**Step 2: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py -k coverage_frontier_probe --import-mode=importlib`

Expected: FAIL because the policy layer does not exist yet.

**Step 3: Write the failing no-budget test**

Add a regression proving the frontier is skipped when the remaining request budget is too small.

Expected assertion:

```python
assert result.response.answer_status == "insufficient_evidence"
assert not any(
    entry["stage"] == "coverage_frontier_probe"
    for entry in result.runtime_trace.retrieval_trace
)
```

**Step 4: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py -k coverage_frontier_skips_when_budget_low --import-mode=importlib`

Expected: FAIL because the new gate does not exist yet.

**Step 5: Write the failing deepen-one-branch test**

Add a regression proving that if two frontier candidates are considered but only one has strong alignment, the pipeline deepens only that branch once and records a dedicated trace stage.

Expected assertion:

```python
assert sum(
    1 for entry in result.runtime_trace.retrieval_trace
    if entry["stage"] == "coverage_frontier_deepen"
) == 1
```

**Step 6: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py -k coverage_frontier_deepen --import-mode=importlib`

Expected: FAIL because deepen logic does not exist yet.

**Step 7: Commit**

Do not commit yet. Wait until implementation and verification pass.

---

### Task 2: Add retrieval-policy primitives and configuration

**Files:**
- Create: `skill/synthesis/retrieval_policy.py`
- Modify: `skill/config/retrieval.py`
- Test: `tests/test_answer_runtime_budget.py`

**Step 1: Write minimal policy data structures**

Create `skill/synthesis/retrieval_policy.py` with:

- a `CoverageFrontierProbe` dataclass
- helper functions for:
  - remaining-budget gating
  - frontier candidate generation
  - frontier winner selection
  - sufficiency decision

Keep v1 deterministic. Do not add any model call.

**Step 2: Add minimal configuration constants**

Extend `skill/config/retrieval.py` with constants for:

- frontier max probes
- per-probe timeout
- minimum remaining seconds required to probe
- minimum alignment needed to deepen
- initial complementary-route source choices

Keep the initial scope limited to `policy <-> industry`.

**Step 3: Run targeted tests**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py -k "coverage_frontier_probe or coverage_frontier_skips_when_budget_low or coverage_frontier_deepen" --import-mode=importlib`

Expected: still FAIL or partially FAIL because orchestration is not integrated yet, but imports and policy helpers should load cleanly.

**Step 4: Commit**

Do not commit yet. Integration is still missing.

---

### Task 3: Integrate the policy layer into answer orchestration

**Files:**
- Modify: `skill/synthesis/orchestrate.py`
- Reference: `skill/retrieval/orchestrate.py`
- Reference: `skill/orchestrator/budget.py`
- Test: `tests/test_answer_runtime_budget.py`

**Step 1: Insert the policy hook at the right point**

In `execute_answer_pipeline_with_trace(...)`, integrate the new policy after:

- primary retrieval
- canonical evidence shaping
- local fast-path miss

and before:

- relevance-gated early stop
- model synthesis

The policy hook should:

1. inspect primary evidence and remaining budget
2. build the frontier when eligible
3. execute up to two bounded frontier probes
4. optionally deepen one winning branch once
5. rebuild local answer candidacy from the augmented evidence

**Step 2: Reuse internal tracing**

Append internal benchmark-only trace entries with new stages:

- `coverage_frontier_probe`
- `coverage_frontier_deepen`

Do not change the public response schema.

**Step 3: Keep fallback bounded**

Make sure the integration cannot:

- reopen heavy first-hop `mixed`
- recurse indefinitely
- fan out beyond the new configured cap

The implementation should be one bounded breadth step plus at most one bounded deepen step.

**Step 4: Run targeted tests**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py -k "coverage_frontier_probe or coverage_frontier_skips_when_budget_low or coverage_frontier_deepen" --import-mode=importlib`

Expected: PASS

**Step 5: Run the full answer-runtime regression file**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_answer_runtime_budget.py --import-mode=importlib`

Expected: PASS

**Step 6: Commit**

```bash
git add skill/config/retrieval.py skill/synthesis/retrieval_policy.py skill/synthesis/orchestrate.py tests/test_answer_runtime_budget.py
git commit -m "feat: add coverage-first retrieval policy"
```

---

### Task 4: Re-verify retained route and retrieval contracts

**Files:**
- Test: `tests/test_route_contracts.py`
- Test: `tests/test_intent_task2.py`
- Test: `tests/test_industry_source_split.py`
- Test: `tests/test_academic_live_adapters.py`
- Test: `tests/test_retrieval_query_variants.py`

**Step 1: Run the retained handoff regression suite**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_route_contracts.py tests/test_intent_task2.py tests/test_industry_source_split.py tests/test_answer_runtime_budget.py tests/test_academic_live_adapters.py tests/test_retrieval_query_variants.py --import-mode=importlib`

Expected: PASS

**Step 2: Inspect failures before changing anything else**

If any existing retained test fails:

- stop
- identify whether the failure is a real design conflict or a narrow bug in the new policy hook
- fix the policy hook, not the benchmark expectation

**Step 3: Commit**

If code changes were required, make a follow-up commit:

```bash
git add skill/synthesis/orchestrate.py skill/synthesis/retrieval_policy.py tests/test_answer_runtime_budget.py
git commit -m "fix: preserve route contracts under coverage frontier policy"
```

If nothing changed, do not create an extra commit.

---

### Task 5: Run fresh-process artifact-backed validation

**Files:**
- Reference: `scripts/run_benchmark.py`
- Reference: `tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization.json`
- Inspect: `benchmark-results/<new-run>/benchmark-summary.json`
- Inspect: `benchmark-results/<new-run>/benchmark-runs.jsonl`

**Step 1: Build a temporary mixed-only slice**

Run a short script that extracts the existing mixed cases from:

- `tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization.json`

and writes a temporary local JSON file for benchmark input.

**Step 2: Generate a unique cold cache directory**

Run:
`python -c "import uuid; print('.wasc-live-cache-' + uuid.uuid4().hex)"`.

**Step 3: Run fresh-process mixed validation**

Run:
`WASC_RETRIEVAL_MODE=live WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED=0 WASC_LIVE_CACHE_DIR=<generated-dir> python scripts/run_benchmark.py --cases <temp-mixed-slice>.json --runs 1 --output-dir benchmark-results/coverage-frontier-mixed-r1`

Expected:

- artifact directory contains `benchmark-summary.json`
- artifact directory contains `benchmark-runs.jsonl`

**Step 4: Run fresh-process smoke gate**

Run:
`WASC_RETRIEVAL_MODE=live WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED=0 WASC_LIVE_CACHE_DIR=<generated-dir-2> python scripts/run_benchmark.py --smoke-gate --output-dir benchmark-results/coverage-frontier-smoke-r1`

Expected:

- artifact directory contains `benchmark-summary.json`
- artifact directory contains `benchmark-runs.jsonl`

**Step 5: Inspect the result honestly**

Check:

- whether mixed remains `0 / N` or improves
- whether failures shift away from pure timeout
- whether traces now show frontier and single-branch deepen behavior
- whether smoke gate regresses outside mixed

If mixed improves but smoke regresses materially, do not keep the change yet.
If traces improve but score does not move, record that explicitly and stop instead of layering on more heuristics.

**Step 6: Commit**

Do not commit benchmark artifacts.

