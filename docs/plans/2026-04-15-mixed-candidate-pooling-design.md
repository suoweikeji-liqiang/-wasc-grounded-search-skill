# Mixed Candidate Pooling Design

**Date:** 2026-04-15

**Goal:** Improve mixed-query generalization by splitting mixed retrieval into a shallow candidate discovery phase and a narrow deep-enrichment phase, so the system spends more of its deadline on the best cross-domain candidates instead of timing out during broad early fetches.

## Problem

The v43 provenance-aware mixed evidence assembly round improved downstream pairing, but it also clarified that the main mixed bottleneck has moved earlier in the pipeline.

Observed benchmark state after v43:

- local guardrail improved to `44 / 50`
- fresh holdout 1 improved to `29 / 50`
- fresh holdout 2 improved to `30 / 50`
- but `gen2 mixed` remained `0 / 10`
- and many remaining mixed failures are still `retrieval_failure + timeout`

That means the current mixed path often fails before evidence assembly even matters.

The root cause is structural:

- `industry_ddgs` and `policy_official_registry` already perform expensive deep actions during their normal `search()` flow
- mixed queries run those heavy adapters too early
- the deadline gets consumed before both route branches can surface viable candidates

So the next improvement should not be "more variants" or "more markers." It should be:

- find cheap candidates first
- choose a small cross-domain shortlist
- spend deep fetch budget only on the shortlist

## Constraints

- No new sample-specific keyword tables or regex patching as the main strategy
- Mixed route only for the first version
- Keep non-mixed route behavior stable
- Preserve the existing retrieval-to-evidence contract where possible
- Use only local code paths; no remote MCP dependence
- The user explicitly approved relaxing mixed budget from `6s` to `8s`

## Options Considered

### 1. Engine-only pooling without splitting adapters

Pros:
- Smallest code churn

Cons:
- Misleadingly shallow: current adapter `search()` methods already perform heavy fetch/enrichment internally
- Pooling at the engine layer alone would still pay most of the deep cost too early

### 2. Recommended: split mixed adapters into discovery and deep-enrichment phases

Pros:
- True shallow-first architecture
- Lets mixed retrieval discover policy and supplemental candidates cheaply
- Deep work is reserved for a small shortlist only
- Keeps the current evidence pipeline mostly unchanged

Cons:
- Requires changes in engine, plan budgets, and two adapters
- Needs deterministic fallback rules so mixed does not become brittle

### 3. Generic SERP pooling layer above all adapters

Pros:
- Uniform and easy to reason about

Cons:
- Weak for official policy sources and SEC-style sources where existing structure already matters
- Risks throwing away current official-source advantages

## Recommended Design

### 1. Add a mixed-only shallow-first retrieval path

Inside `skill/retrieval/engine.py`, add a mixed-specific execution path that is only used when:

- `plan.route_label == "mixed"`
- both `primary_route` and `supplemental_route` are present
- the mixed pooled path is enabled by plan configuration

The new path should execute:

1. route-specific variant generation
2. shallow discovery on primary + supplemental branches
3. pooled shortlist selection
4. deep enrichment on shortlist only
5. existing evidence pipeline

Non-mixed retrieval should continue using the current path unchanged.

### 2. Split mixed adapter behavior into `discover` and `enrich`

For first version, only split the adapters that matter most for current mixed failures:

- `skill/retrieval/adapters/policy_official_registry.py`
- `skill/retrieval/adapters/industry_ddgs.py`

Each should expose two internal layers:

- `discover_candidates(...)`
  - cheap only
  - no page fetch
  - no query-aligned page excerpt
  - no SEC archive deep fetch
  - returns lightweight candidate metadata

- `enrich_candidates(...)`
  - operates on a small preselected candidate list
  - may call the current expensive fetch/excerpt logic
  - returns final `RetrievalHit` objects

This lets the engine orchestrate shallow-first behavior without rewriting the existing deep ranking logic from scratch.

### 3. Introduce a lightweight candidate model

Add a small retrieval-local model, for example in `skill/retrieval/discovery.py`, to represent shallow candidates before they become final `RetrievalHit`s.

Suggested fields:

- `source_id`
- `target_route`
- `title`
- `url`
- `snippet`
- `credibility_tier`
- `provenance`:
  - `variant_reason_codes`
  - `variant_queries`
- `candidate_score`
- `needs_deep_fetch`
- adapter-specific metadata bag if needed

This keeps shallow discovery separate from final enriched hits while preserving the provenance work added in v43.

### 4. Add explicit mixed budget partitioning

Extend `RetrievalPlan` with mixed-specific budget fields instead of hardcoding them in the engine.

First retained budget proposal:

- `mixed_overall_deadline_seconds = 8.0`
- `mixed_discovery_deadline_seconds = 2.5`
- `mixed_shortlist_top_k = 4`
- `mixed_deep_deadline_seconds = 5.0`

Optional supporting field:

- `mixed_discovery_per_source_timeout_seconds = 1.0` or similar bounded value

This makes tuning testable and prevents the engine from hiding budget decisions.

### 5. Shortlist by route-local fragment alignment

The pooled shortlist should use the v43 provenance machinery:

- primary candidates rank by alignment to primary-side fragment queries
- supplemental candidates rank by alignment to supplemental-side fragment queries
- full-query alignment remains a tiebreaker

Shortlist guardrails:

- reserve at least one primary candidate if any exist
- reserve at least one supplemental candidate if any exist
- then fill remaining slots by total candidate score

This preserves mixed complementarity before deep enrichment starts.

### 6. Fallback and degradation rules

The new pooled path must be an additive improvement layer, not a brittle replacement.

Rules:

- if discovery finds a usable dual-route shortlist, use the pooled path
- if discovery only finds single-route or empty candidates, fall back to the current mixed retrieval path using only remaining time
- if deep enrichment times out, keep shallow candidates instead of discarding them
- if one adapter lacks split support, use existing `search()` only for that source and keep pooled behavior for the other route

This preserves current stability while still allowing incremental rollout.

## Data Flow

`mixed query`
-> route-specific variants
-> primary discovery + supplemental discovery
-> pooled candidate set
-> route-aware shortlist
-> deep enrichment on top-K
-> final `RetrievalHit`
-> existing normalization / canonicalization / evidence packing

## Files To Change

- `skill/orchestrator/retrieval_plan.py`
- `skill/retrieval/engine.py`
- `skill/retrieval/discovery.py` or equivalent new helper module
- `skill/retrieval/adapters/policy_official_registry.py`
- `skill/retrieval/adapters/industry_ddgs.py`
- `tests/test_retrieval_query_variants.py`
- `tests/test_retrieval_integration.py`
- `tests/test_policy_live_adapters.py`
- `tests/test_industry_live_adapter.py`
- `tests/test_mixed_candidate_pooling.py` (recommended new focused test file)

## Verification

### Unit / integration

- prove mixed pooled path builds a dual-route shortlist under tight budgets
- prove discovery path does not trigger deep fetch functions
- prove deep-enrichment timeout still preserves shallow hits
- prove non-mixed retrieval remains unchanged

### Benchmark

Success criteria for this round:

- local guardrail does not materially regress from v43
- `gen2 mixed` improves above `0 / 10`
- mixed failure mix shifts away from raw `timeout`

Primary benchmark comparisons:

- `benchmark-results/generated-hidden-like-r1-v43-local/`
- `benchmark-results/generated-hidden-like-r1-v43-generalization/`
- `benchmark-results/generated-hidden-like-r1-v43-generalization-round2/`

## Why This Direction Is Generalization-First

This design does not depend on enumerating domain-specific markers.
It changes the retrieval shape:

- broader early recall
- narrower late spending
- fragment-aware cross-domain ranking

That is a better fit for unseen mixed questions than continuing to patch query text with more route-specific heuristics.
