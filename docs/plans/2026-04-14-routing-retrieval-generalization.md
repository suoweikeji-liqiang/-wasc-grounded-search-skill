# Routing And Retrieval Generalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve route selection and live retrieval robustness for realistic public-source benchmark queries without adding query-specific special cases.

**Architecture:** Tighten route selection so `mixed` is reserved for true cross-domain cases, then reduce live-retrieval timeout risk by trusting structured official/public result metadata earlier. The work stays inside the existing route classifier and live adapters rather than adding new subsystems.

**Tech Stack:** Python, FastAPI, pytest, async retrieval adapters

---

### Task 1: Add routing regressions

**Files:**
- Modify: `tests/test_intent_task2.py`
- Modify: `tests/test_route_contracts.py`

**Steps:**

1. Write failing tests for hidden-like English policy, academic, and industry queries that currently collapse to `mixed`.
2. Run only the new routing tests and confirm they fail for the current classifier.
3. Keep the existing `short_query` and true `low_signal` ambiguous behaviors covered.

### Task 2: Add live policy fallback regressions

**Files:**
- Modify: `tests/test_policy_live_adapters.py`

**Steps:**

1. Write a failing test showing an official EUR-Lex or other official-domain candidate can still produce a hit when page fetch yields no text but the search result itself is strong.
2. Run that test alone and confirm it fails.

### Task 3: Add SEC structured-hit regression

**Files:**
- Modify: `tests/test_industry_live_adapter.py`

**Steps:**

1. Write a failing test showing SEC EDGAR structured results should be returned without a second page fetch.
2. Run that test alone and confirm it fails.

### Task 4: Implement minimal routing changes

**Files:**
- Modify: `skill/orchestrator/intent.py`
- Modify: `skill/orchestrator/query_traits.py`

**Steps:**

1. Add generic English route hints for official policy text, company filing/earnings language, and academic research queries.
2. Change the low-signal fallback so weak but single-domain queries route concrete instead of defaulting to `mixed`.
3. Re-run the routing tests and confirm they pass.

### Task 5: Implement minimal live adapter changes

**Files:**
- Modify: `skill/retrieval/live/parsers/policy.py`
- Modify: `skill/retrieval/adapters/policy_official_registry.py`
- Modify: `skill/retrieval/adapters/industry_ddgs.py`

**Steps:**

1. Expand official policy domain coverage for common EU, UK, and US public sources.
2. Let official policy search results survive with domain-derived authority and candidate-level metadata when page fetch enrichment is missing.
3. Use SEC structured filing hits directly without mandatory page fetch.
4. Keep page fetch as enrichment, not a hard dependency.
5. Run the targeted adapter tests and confirm they pass.

### Task 6: Verify generalized impact

**Files:**
- Modify: none

**Steps:**

1. Run the focused test suites for routing and live adapters.
2. Run the full test suite.
3. Re-run the generated hidden-like benchmark and compare summary metrics against the previous `0 grounded_success` baseline.
