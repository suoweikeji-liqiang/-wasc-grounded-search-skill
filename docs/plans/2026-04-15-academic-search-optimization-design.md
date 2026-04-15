# Academic Search Optimization Design

**Date:** 2026-04-15

**Goal:** Improve academic retrieval on long technical queries by generating a small, more orthogonal search portfolio before source execution, without changing the public retrieval API or adding adapter-specific special cases.

## Problem

The current academic path already has condensed variants, but the remaining misses in the latest local benchmark still cluster around the same shape:

- retrieval returns `partial`
- at least one academic source times out
- retained evidence is too generic or off-center to ground the answer

The current variant set is still too narrow for those cases:

- `original`
- `academic_topic_focus`
- `academic_source_hint`
- generic `paper research` / `survey benchmark`

That helps recall a bit, but it still does not create a real portfolio of different search angles for queries such as:

- `arXiv test-time scaling ... best-of-n reranking`
- `DiT consistency distillation accelerated sampling`
- `Europe PMC single-cell foundation model ... cell type annotation`
- `LLM watermarking robustness to paraphrasing false-positive rate`

## Constraints

- Academic route only for the first version
- Pure function query shaping only
- No new public API
- Small runtime budget only: keep the default 3 total academic variants during execution
- Extra academic variants may still exist as overflow candidates for experiments or explicit larger budgets, but they should not displace the stable runtime path by default
- No benchmark-ID hardcoding
- Avoid globally adding quotes or tightening every academic query

## Options Considered

### 1. Keep tuning adapter-local ranking and timeouts

Pros:
- Small localized edits

Cons:
- The handoff and latest benchmark both suggest the bottleneck is query shape mismatch more than adapter mechanics
- Previous timeout slicing already showed unstable benchmark behavior

### 2. Expand the current condensed-topic logic only

Pros:
- Minimal code churn

Cons:
- Still mostly produces one academic angle plus boilerplate lookups
- Does not add a bounded portfolio planner

### 3. Recommended: add a bounded academic search-optimization portfolio

Pros:
- Route-local and pure-function
- Lets retrieval try genuinely different academic query shapes under the same time budget
- Matches the current failure pattern without touching adapters again

Cons:
- Slightly more planning logic
- Needs careful prioritization so it does not just add noise

## Recommended Design

Add a small academic-only portfolio planner inside retrieval query shaping.

For academic execution, keep the original query and then optionally derive:

- `academic_source_hint`: condensed query that preserves explicit repository hints such as `arXiv` or `Europe PMC`
- `academic_phrase_locked`: condensed query that quotes one or two strong technical phrases, primarily hyphenated noun phrases such as `test-time scaling`, `best-of-n reranking`, `single-cell foundation model`, or `false-positive rate`
- `academic_evidence_type_focus`: shorter query that keeps the main topic while emphasizing explicit evidence-type language already present in the user query, such as `dataset`, `benchmark`, `evaluation`, `survey`, `comparison`, `annotation`, or `citation`
- `academic_topic_focus`: the current condensed topical query as a fallback broad-but-short variant

Execution should keep the portfolio bounded:

- retain the default runtime `query_variant_budget = 3`
- change which academic variants occupy those slots instead of simply adding more slots
- prioritized execution order should prefer `source_hint`, then `topic_focus`, then `phrase_locked`, then `original`, with `evidence_type_focus` kept as a lower-priority overflow variant

This still shares the existing per-source timeout budget; it only spends that budget on better ordered academic search attempts.

## Empirical Update

An intermediate experiment that increased the academic runtime budget from `3` to `4` variants regressed the hidden-like benchmark and was discarded. The retained design keeps the search-preprocessing layer but not the larger runtime budget.

## Files To Change

- `skill/retrieval/query_variants.py`
- `skill/retrieval/engine.py`
- `skill/orchestrator/retrieval_plan.py`
- `tests/test_retrieval_query_variants.py`

## Verification

- Add failing tests for new academic variant shapes
- Add failing tests for academic execution priority under a tight timeout budget
- Run focused `tests/test_retrieval_query_variants.py`
- If stable, run the full retrieval-variant focused suite or full tests
