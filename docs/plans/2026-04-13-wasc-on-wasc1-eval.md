# WASC On WASC1 Eval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the current `D:\study\WASC` implementation against `D:\study\WASC1`'s 12-case competition evaluation dataset and scoring rules.

**Architecture:** Add one local evaluation script in `D:\study\WASC` that loads `D:\study\WASC1\ref\competition_eval_cases.json`, executes the current `WASC` `/answer` path through `FastAPI TestClient`, normalizes the result into a summary/key-points/sources/uncertainties shape, and computes the same aggregate metrics used by `WASC1`'s competition-style evaluator.

**Tech Stack:** Python, FastAPI TestClient, JSON reporting, existing WASC API, external WASC1 eval dataset.

---

### Task 1: Add the cross-evaluation script

**Files:**
- Create: `scripts/run_wasc_on_wasc1_eval.py`

**Step 1: Write minimal implementation**

Implement:

- WASC1 case loader
- current WASC `/answer` executor
- result normalization into `summary`, `key_points`, `sources`, `uncertainties`
- aggregate report writer

**Step 2: Run help**

Run: `python .\scripts\run_wasc_on_wasc1_eval.py --help`
Expected: usage output with dataset and output options.

### Task 2: Validate on a smoke subset

**Files:**
- Modify: `scripts/run_wasc_on_wasc1_eval.py` if smoke execution exposes normalization bugs

**Step 1: Run first 2-3 cases**

Run: `python .\scripts\run_wasc_on_wasc1_eval.py --max-cases 3`
Expected: report is written and console summary prints route, latency, and keyword metrics.

### Task 3: Run full 12-case evaluation

**Files:**
- Create: `benchmark-results/wasc-on-wasc1-eval-report.json`

**Step 1: Execute full run**

Run: `python .\scripts\run_wasc_on_wasc1_eval.py --dataset D:\study\WASC1\ref\competition_eval_cases.json --output benchmark-results/wasc-on-wasc1-eval-report.json`
Expected: JSON report written with per-case details and aggregate summary.

### Task 4: Commit the comparison artifacts

**Files:**
- `scripts/run_wasc_on_wasc1_eval.py`
- `benchmark-results/wasc-on-wasc1-eval-report.json`

**Step 1: Commit**

```bash
git add scripts/run_wasc_on_wasc1_eval.py benchmark-results/wasc-on-wasc1-eval-report.json
git commit -m "feat: add WASC evaluation against WASC1 competition cases"
```
