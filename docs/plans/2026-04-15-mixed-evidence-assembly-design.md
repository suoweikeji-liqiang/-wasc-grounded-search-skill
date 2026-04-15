# Mixed Evidence Assembly Design

**Date:** 2026-04-15

**Goal:** Improve mixed-query generalization by carrying query-variant provenance through retrieval and using route-local fragment alignment to select complementary evidence, instead of relying on source-family heuristics or more sample-specific marker expansion.

## Problem

The current mixed pipeline retrieves more broadly than before, but the evidence layer still collapses most of that extra signal:

- `run_retrieval()` merges hits across variants without preserving which variant produced the hit
- `normalize_hit_candidates()` assigns `route_role` only from `source_id`
- mixed ordering and seeding score records against the full user query, even when a record only answers one sub-question well

That creates a structural mismatch on mixed queries such as policy + vendor / regulator + company / rule + research:

- policy records get penalized for not matching the business fragment
- industry or academic records get penalized for not matching the policy fragment
- the pack keeps "globally similar" records instead of the best complementary pair

## Constraints

- No new sample-specific keyword tables or regex patches as the main mechanism
- Keep the current route classifier intact
- Preserve the existing bounded retrieval budget model
- Avoid remote MCP dependence
- Prefer changes that can generalize across future mixed query shapes

## Options Considered

### 1. Add more mixed markers or route-specific regexes

Pros:
- Fast local gains on individual failures

Cons:
- High overfitting risk
- Does not address why structurally good presearch still collapses downstream

### 2. Increase query-variant budgets again without changing evidence assembly

Pros:
- Minimal code churn

Cons:
- More search attempts do not help much if later stages forget which fragment each hit matched
- Risks extra latency without improving mixed evidence pairing

### 3. Recommended: provenance-driven mixed evidence assembly

Pros:
- Structural fix at the retrieval-to-evidence boundary
- Lets mixed ranking prefer the best policy fragment and best supplemental fragment independently
- Works with the broader presearch direction already added

Cons:
- Requires model changes across retrieval and evidence layers
- Needs careful deterministic scoring to avoid noisy ordering

## Recommended Design

### 1. Preserve variant provenance on retrieval hits

Each hit returned from `_run_source_variants()` should keep:

- `target_route`
- `variant_reason_code`
- `variant_query`

When the same hit appears across multiple variants, dedupe should merge provenance instead of discarding it.

### 2. Carry provenance into raw evidence

`RawEvidenceRecord` should preserve the hit provenance so later layers can inspect:

- which route-specific branch retrieved the record
- which focused query fragment matched it
- whether the hit came from a structural fragment variant versus the original broad query

### 3. Score mixed records by route-local focus, not only full-query overlap

For mixed ordering and seeding:

- primary records should be ranked by the best alignment to their recorded primary-side focus query
- supplemental records should be ranked by the best alignment to their recorded supplemental-side focus query
- full-query alignment should remain a tiebreaker, not the only relevance signal

This should let the pipeline prefer complementary records that each answer one side of the mixed question well.

### 4. Seed the pack with the best complementary pair

`_seed_mixed_coverage_records()` should use provenance-aware route-local scores so the first pair is:

- strongest primary-side fragment record
- strongest supplemental-side fragment record

not merely the highest full-query record from each source family.

## Files To Change

- `skill/retrieval/models.py`
- `skill/retrieval/engine.py`
- `skill/evidence/models.py`
- `skill/evidence/normalize.py`
- `skill/evidence/score.py`
- `skill/retrieval/orchestrate.py`
- `tests/test_evidence_models.py`
- `tests/test_evidence_pack.py`
- `tests/test_retrieval_integration.py`

## Verification

- Add failing tests for provenance preservation from retrieval hit to raw evidence
- Add failing tests showing mixed ranking prefers fragment-aligned complementary evidence over broad but less complementary evidence
- Run focused tests for retrieval/evidence integration
- Run the full suite
- Re-run local plus fresh generalization benchmarks and update `HANDOFF.md`
