# Implementation Comparison Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and run a shared 10-case benchmark comparison between `D:\study\WASC` and `D:\study\WASC1`.

**Architecture:** Add one comparison script inside `D:\study\WASC` that loads the existing locked benchmark manifest, runs both implementations through thin adapters, normalizes their outputs into one schema, and writes an aggregate JSON report. Keep all changes inside the current repo and do not modify `D:\study\WASC1`.

**Tech Stack:** Python, FastAPI TestClient, existing WASC benchmark manifest, direct import of `WASC1` modules, JSON reporting, pytest if needed.

---

### Task 1: Add normalized comparison models and script scaffold

**Files:**
- Create: `scripts/compare_impls.py`

**Step 1: Write the failing test**

Skip for this task. This script can be verified by execution because it bridges two repositories and existing benchmark manifests.

**Step 2: Write minimal implementation**

Create:

- manifest loader
- normalized per-run record model or dict builder
- adapter hooks for current `WASC` and external `WASC1`
- JSON report writer

**Step 3: Run script help**

Run: `python .\scripts\compare_impls.py --help`
Expected: usage output with dataset and output options.

**Step 4: Commit**

```bash
git add scripts/compare_impls.py
git commit -m "feat: add shared implementation comparison script"
```

### Task 2: Wire current WASC benchmark execution

**Files:**
- Modify: `scripts/compare_impls.py`

**Step 1: Implement WASC runner**

Use:

- `skill.api.entry.app`
- `fastapi.testclient.TestClient`
- `/answer`
- `app.state.last_runtime_trace`

Collect:

- route label
- answer status
- elapsed ms
- source count
- uncertainty count

**Step 2: Dry-run on one case**

Run: `python .\scripts\compare_impls.py --impl wasc --max-cases 1`
Expected: one-case JSON summary written successfully.

**Step 3: Commit**

```bash
git add scripts/compare_impls.py
git commit -m "feat: add WASC comparison adapter"
```

### Task 3: Wire WASC1 benchmark execution

**Files:**
- Modify: `scripts/compare_impls.py`

**Step 1: Implement WASC1 runner**

Import from `D:\study\WASC1`:

- `skill.main.run_query`
- `skill.router.classify_query`

Measure:

- route label from `classify_query(query)`
- elapsed ms around `run_query(query)`
- source count from `sources`
- uncertainty count from `uncertainties`
- summary preview from `summary`

**Step 2: Dry-run on one case**

Run: `python .\scripts\compare_impls.py --impl wasc1 --max-cases 1`
Expected: one-case JSON summary written successfully.

**Step 3: Commit**

```bash
git add scripts/compare_impls.py
git commit -m "feat: add WASC1 comparison adapter"
```

### Task 4: Run full shared comparison and save artifacts

**Files:**
- Modify: `scripts/compare_impls.py` only if execution exposes normalization bugs
- Create: `benchmark-results/impl-comparison-summary.json`

**Step 1: Execute both implementations**

Run: `python .\scripts\compare_impls.py --dataset tests/fixtures/benchmark_phase5_cases.json --output benchmark-results/impl-comparison-summary.json`

Expected:

- script finishes
- JSON report written
- console output summarizes both implementations

**Step 2: Inspect report**

Verify aggregate fields:

- route accuracy
- average latency
- p95 latency
- average sources
- uncertainty rate

**Step 3: Commit**

```bash
git add scripts/compare_impls.py benchmark-results/impl-comparison-summary.json
git commit -m "docs: record shared implementation comparison baseline"
```

### Task 5: Summarize findings

**Files:**
- No file required unless a follow-up report is useful

**Step 1: Compare outcomes**

Report:

- which implementation is faster
- which implementation routes more accurately
- whether `WASC1` clears the current locked baseline acceptably
- where the two architectures differ materially

**Step 2: Surface next actions**

Recommend whether to:

- keep `WASC` as primary
- port ideas from `WASC1`
- or run a deeper side-by-side benchmark later
