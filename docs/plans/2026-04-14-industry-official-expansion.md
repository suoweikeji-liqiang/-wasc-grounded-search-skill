# Industry Official Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve hidden-like benchmark coverage for `industry` queries by adding structural official-source fan-in and cheaper early ranking for official candidates.

**Architecture:** Keep the existing `industry_ddgs` adapter as the single industry source, but let it merge direct official candidates for common official/company/specification ecosystems before or alongside generic multi-engine search. Preserve the current ranking model and only add structural source detection, candidate shaping, and enrichment shortcuts that reduce timeout risk.

**Tech Stack:** Python, pytest, async retrieval adapters

---

### Task 1: Add failing regressions for official direct candidates

**Files:**
- Modify: `tests/test_industry_live_adapter.py`

**Steps:**

1. Write a failing test showing an RFC-style official query can return an official standards hit without depending on generic search results.
2. Write a failing test showing an association or regulator official query can merge a direct official hit ahead of weaker generic results.
3. Run only the new tests and confirm they fail for the current implementation.

### Task 2: Implement direct official-source fan-in

**Files:**
- Modify: `skill/retrieval/adapters/industry_ddgs.py`

**Steps:**

1. Add structural query detection for official company filings, standards/specification references, and association forecast pages.
2. Build direct candidates from official ecosystems such as SEC, RFC Editor/IETF, W3C, Chromium, and association/company domains when the query has clear signals.
3. Merge those candidates with multi-engine results without bypassing the existing relevance scoring.
4. Re-run the new adapter tests and confirm they pass.

### Task 3: Reduce enrichment cost for clearly strong official hits

**Files:**
- Modify: `skill/retrieval/adapters/industry_ddgs.py`

**Steps:**

1. Skip page-fetch enrichment when a direct or search candidate is already official and strongly aligned to the query.
2. Preserve current page-fetch fallback for weaker or generic candidates.
3. Run the industry adapter test file and confirm all tests pass.

### Task 4: Verify retrieval safety and impact

**Files:**
- Modify: none

**Steps:**

1. Run the targeted industry adapter tests.
2. Run the related answer-runtime regression slice.
3. If the targeted tests pass, run a benchmark smoke command or inspect impact via the next local benchmark run.
