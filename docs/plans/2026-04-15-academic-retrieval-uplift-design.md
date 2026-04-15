# Academic Retrieval Uplift Design

**Date:** 2026-04-15

**Goal:** Improve academic benchmark coverage without falling back to case-specific hacks, while preserving the current browser-free routed retrieval architecture and keeping latency bounded.

## Problem

The current academic path is failing for three different reasons:

1. Live academic adapters still allow fixture shortcuts in `live` mode, and the shortcut gate is too permissive.
   - Some academic queries short-circuit to irrelevant deterministic fixtures because generic route terms like `retrieval`, `evaluation`, or `benchmark` are enough to clear the current threshold.
   - This produces fast but weak evidence, which then misses the local grounded-answer fast path and burns synthesis budget.
2. Academic query variants only append broad words like `paper research` or `survey benchmark`.
   - For long realistic queries, structured sources often need a tighter topical query, not a longer one.
   - Current variants do not drop years, source-brand words, or lookup boilerplate, so they do little to improve recall.
3. The academic local fast path is too conservative for clipped but still clearly aligned evidence.
   - We already have retrieved academic evidence for some cases, but the overlap gate does not promote it to a local grounded response.
   - The request then falls through to model synthesis and can fail on runtime budget instead of returning a bounded grounded answer.

## Non-Goals

- No benchmark-case hardcoding by `case_id`, exact full-query match, or static case tables.
- No new browser automation or Playwright dependence.
- No broad rewrite of evidence normalization or citation validation.
- No expansion into a chat-first academic summarizer.

## Approaches Considered

### 1. Disable academic fixture shortcuts entirely

Pros:
- Removes false positive shortcut hits immediately.

Cons:
- Current live scholarly retrieval is not strong enough on its own for many queries.
- This would trade bad matches for frequent full retrieval failure and timeout-heavy misses.

### 2. Expand academic fixtures to cover the observed misses

Pros:
- Fastest path to higher local benchmark numbers.

Cons:
- Too close to benchmark-shape overfitting.
- Weakens confidence that changes will generalize beyond the generated hidden-like suite.

### 3. Recommended: tighten shortcut admission and improve real retrieval/query shaping

Pros:
- Fixes the current false-positive shortcut behavior.
- Gives live academic sources a better chance to surface relevant papers.
- Preserves fast local grounded responses when evidence is already good enough.

Cons:
- Slightly more implementation work than simply editing the fixture list.

## Recommended Design

### 1. Tighten academic fixture shortcut gating

Keep fixture shortcuts available, but only when the match is genuinely topic-aligned.

The gate should require:

- stronger content overlap than the current raw alignment threshold
- at least one non-generic topical term overlap beyond broad academic words
- preference for shortcut hits whose title or snippet carries the user’s real focus terms

The intent is:

- easy known academic lookups can still resolve instantly
- generic academic words alone no longer unlock irrelevant shortcuts

### 2. Add condensed academic query variants

Add a route-specific academic condensation step before retrieval:

- preserve the original query
- add one shorter topic-focused academic query
- optionally add one source-hinted academic query when the user explicitly says `arXiv`, `Europe PMC`, or similar

The condensed query should:

- remove year clutter when it is not the core discriminator
- remove academic boilerplate terms like `paper`, `papers`, `research`, `evaluation` when they only lengthen the query
- preserve the strongest topical tokens and phrases such as `mixture-of-experts`, `load balancing`, `hallucination reduction`, `RoPE scaling`, `single-cell`, `watermarking`, and similar domain terms

This stays structural because it is driven by token classes and query traits, not by benchmark IDs.

### 3. Promote high-overlap academic evidence to a local answer more often

When retrieval is already successful and academic canonical evidence contains clearly query-aligned retained slices, prefer a local grounded response instead of spending model budget.

Refinement:

- allow the academic fast path to trigger when the best retained slice has strong topic overlap even if the overall evidence pack was clipped
- keep citation validation unchanged
- keep the bar conservative enough that irrelevant generic academic snippets still fail closed

This should directly address the current `retrieval succeeded, then synthesis budget failed` pattern.

## Files Likely To Change

- `skill/retrieval/query_variants.py`
- `skill/retrieval/adapters/academic_asta_mcp.py`
- `skill/retrieval/adapters/academic_semantic_scholar.py`
- `skill/retrieval/adapters/academic_arxiv.py`
- `skill/retrieval/adapters/academic_live_common.py`
- `skill/synthesis/orchestrate.py`
- `tests/test_retrieval_query_variants.py`
- `tests/test_academic_live_adapters.py`
- `tests/test_answer_runtime_budget.py`

## Verification Strategy

Add failing tests first for:

- condensed academic query variants on long benchmark-like queries
- fixture shortcut rejection when only generic academic overlap exists
- local academic fast-path success when retrieved evidence is clipped but still strongly aligned

Then run:

- focused academic adapter and runtime-budget tests
- the full test suite
- one updated hidden-like benchmark run to compare against the `v15` baseline

## Success Criteria

- Long academic queries generate at least one shorter topic-focused retrieval variant.
- Irrelevant academic fixture shortcuts no longer beat live retrieval on generic benchmark-like wording.
- At least one current `retrieval success but synthesis budget failure` academic pattern becomes a grounded local response.
- No regression to the existing industry and policy fixes.
