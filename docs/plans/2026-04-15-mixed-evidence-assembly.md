# Mixed Evidence Assembly Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make mixed retrieval preserve query-fragment provenance and use that provenance to assemble complementary primary/supplemental evidence more reliably on unseen queries.

**Architecture:** Extend retrieval hits with variant provenance, propagate that provenance into raw evidence records, and change mixed ordering/seeding to score records by route-local focus-query alignment. Keep the classifier and bounded retrieval plan intact; improve the retrieval-to-evidence contract instead of adding more route markers.

**Tech Stack:** Python, pytest, FastAPI, existing retrieval/evidence pipeline

---

### Task 1: Add failing provenance and mixed-ranking regression tests

**Files:**
- Modify: `tests/test_evidence_models.py`
- Modify: `tests/test_evidence_pack.py`
- Modify: `tests/test_retrieval_integration.py`

**Step 1: Write a failing test proving retrieval provenance survives into normalized raw evidence**

**Step 2: Write a failing test proving mixed scoring prefers fragment-aligned complementary records over broad full-query overlap**

**Step 3: Write a failing integration test for mixed pipeline ordering with route-local fragment provenance**

**Step 4: Run focused tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_evidence_models.py tests/test_evidence_pack.py tests/test_retrieval_integration.py --import-mode=importlib`
Expected: FAIL on the new mixed provenance assertions.

### Task 2: Preserve query-variant provenance through retrieval execution

**Files:**
- Modify: `skill/retrieval/models.py`
- Modify: `skill/retrieval/engine.py`

**Step 1: Extend retrieval hit models with target-route and variant provenance fields**

**Step 2: Annotate hits with provenance inside `_run_source_variants()`**

**Step 3: Merge provenance when duplicate hits are seen across multiple variants**

### Task 3: Carry provenance into evidence normalization and mixed scoring

**Files:**
- Modify: `skill/evidence/models.py`
- Modify: `skill/evidence/normalize.py`
- Modify: `skill/evidence/score.py`
- Modify: `skill/retrieval/orchestrate.py`

**Step 1: Add provenance fields to raw evidence records**

**Step 2: Preserve provenance when building raw records from retrieval hits**

**Step 3: Add route-local focus-query scoring helpers for mixed records**

**Step 4: Update mixed ordering and seeded coverage selection to use provenance-aware scores**

### Task 4: Verify regression safety and benchmark effect

**Files:**
- Modify: `HANDOFF.md`
- Artifact: `benchmark-results/generated-hidden-like-r1-v*-*/`

**Step 1: Run focused retrieval/evidence tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_evidence_models.py tests/test_evidence_pack.py tests/test_retrieval_integration.py --import-mode=importlib`
Expected: PASS

**Step 2: Run full suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests --import-mode=importlib`
Expected: PASS

**Step 3: Run benchmark guardrails**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-14.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v43-local`
Expected: local guardrail stays stable enough while mixed evidence ordering improves.

**Step 4: Run fresh holdouts**

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v43-generalization`

Run: `python scripts/run_benchmark.py --cases tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization_round2.json --runs 1 --output-dir benchmark-results/generated-hidden-like-r1-v43-generalization-round2`

Expected: mixed-route transfer improves through better evidence pairing rather than more keyword-specific retrieval patches.
