# Conservative Score Boost Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise competition-facing answer quality metrics through conservative changes to local grounded answer shaping and uncertainty precision.

**Architecture:** Preserve the current `/route` -> `/retrieve` -> `/answer` pipeline. Limit changes to synthesis-layer conclusion construction, uncertainty derivation, and score-focused regressions so the current stable `12/12` evaluation result is not destabilized.

**Tech Stack:** Python, FastAPI, existing synthesis/evidence modules, pytest, benchmark harness

---

### Task 1: Add Score-Focused Failing Regressions

**Files:**
- Modify: `tests/test_answer_runtime_budget.py`
- Modify: `tests/test_competition_eval_end_to_end.py`

**Step 1: Write the failing tests**

Add regressions that verify:

- policy fast-path conclusions include query-critical exemption/change wording when supported by evidence
- industry fast-path conclusions include trend/forecast/shipment wording
- academic fast-path conclusions include research/paper/benchmark wording
- mixed fast-path conclusions include both cross-domain scoring terms
- strong local fast-path answers do not add avoidable uncertainty notes

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_answer_runtime_budget.py tests/test_competition_eval_end_to_end.py -q
```

Expected:

- FAIL on the new score-focused assertions

**Step 3: Commit**

Do not commit yet.

### Task 2: Implement Minimal Synthesis-Layer Changes

**Files:**
- Modify: `skill/synthesis/orchestrate.py`
- Modify: `skill/synthesis/uncertainty.py`

**Step 1: Write minimal implementation**

Implement:

- query-aware conclusion wording helpers for local policy, industry, academic, and mixed fast paths
- stronger reuse of query-critical terms already present in evidence
- uncertainty-note precision so strong local answers avoid non-material notes while real limitations stay visible

Do not:

- change retrieval ordering
- change adapter fixtures
- relax citation checks
- broaden model generation usage

**Step 2: Run focused tests**

Run:

```bash
pytest tests/test_answer_runtime_budget.py tests/test_competition_eval_end_to_end.py -q
```

Expected:

- PASS

**Step 3: Commit**

Do not commit yet.

### Task 3: Re-verify Competition Metrics

**Files:**
- Modify if refreshed: `benchmark-results/wasc-on-wasc1-eval-report.json`

**Step 1: Run the full suite**

Run:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

Expected:

- PASS

**Step 2: Run competition evaluation**

Run:

```bash
python scripts/run_wasc_on_wasc1_eval.py
```

Expected:

- `12/12` remains intact
- uncertainty rate improves if the new tests and synthesis shaping work as intended
- keyword coverage stays at or above the current level

**Step 3: Commit**

```bash
git add -- skill/synthesis/orchestrate.py skill/synthesis/uncertainty.py tests/test_answer_runtime_budget.py tests/test_competition_eval_end_to_end.py benchmark-results/wasc-on-wasc1-eval-report.json docs/plans/2026-04-13-conservative-score-boost-design.md docs/plans/2026-04-13-conservative-score-boost.md
git commit -m "feat: tighten conservative competition answer scoring"
```
