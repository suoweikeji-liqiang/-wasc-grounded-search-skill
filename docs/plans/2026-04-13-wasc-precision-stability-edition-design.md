# WASC Precision / Stability Edition Design

**Date:** 2026-04-13

## Goal

Turn `WASC` into a second, differentiated competition submission that keeps its current strengths in latency, token discipline, explicit answer-state contracts, and repeatability, while closing the biggest generalization gaps exposed by Chinese and mixed-domain competition-style queries.

## Positioning

This version should not become a weaker clone of `WASC1`.

- `WASC1` should remain the broader-coverage submission.
- `WASC` should become the precision/stability submission.
- The scoring thesis for this repo is:
  - win on time, token efficiency, and stability
  - stay strong on groundedness and explicit failure handling
  - improve enough on Chinese and mixed-domain hidden-style queries that it is no longer brittle outside the locked English benchmark

## Current State

Observed strengths:

- deterministic routing and explicit route contracts
- bounded retrieval orchestration
- canonical evidence normalization, dedupe, and evidence packing
- strong answer-state handling: `grounded_success`, `insufficient_evidence`, `retrieval_failure`
- strong repeatability and benchmark telemetry
- very low latency on the locked 10-case benchmark

Observed weaknesses:

- routing is optimized around the locked English benchmark and under-signals Chinese competition phrasing
- retrieval planning is too narrow for hidden-style queries
- mixed-domain coverage is conservative and can fail to surface usable cross-domain evidence
- answer generation is strongly guarded, but many competition-style queries fail before enough evidence is collected
- repeated benchmark runs currently have no quality-aware answer cache to exploit the contest's `10 x 5` repetition structure

## Non-Goals

- do not introduce browser automation into the core path
- do not turn the system into a chat-first agent
- do not expand to a heavy multi-model architecture
- do not widen scope beyond competition-oriented retrieval and answer quality
- do not break existing public API contracts unless strictly necessary

## Architecture

The public architecture remains the same:

- `POST /route`
- `POST /retrieve`
- `POST /answer`

The internal architecture becomes:

1. Route classification with richer query traits
2. Budgeted query planning per route and source
3. Domain-aware retrieval execution and aggregation
4. Stronger mixed-domain evidence ordering and coverage enforcement
5. Local-first answer construction
6. Guarded model synthesis only when local evidence is insufficient
7. Post-generation validation and conservative fallback
8. Quality-gated repeat-run cache

This preserves the current layered design while moving more competition intelligence into routing, retrieval planning, and guarded answer assembly.

## Module Changes

### 1. Routing and Query Traits

Primary files:

- `skill/config/routes.py`
- `skill/orchestrator/intent.py`
- `tests/test_intent_task2.py`
- `tests/test_route_contracts.py`

Changes:

- expand route markers for Chinese and bilingual competition phrasing
- add signals for:
  - policy change / revision / exemption / effective date
  - industry trend / shipment / sales / market share / forecast
  - academic survey / benchmark / review / paper lookup
  - mixed-domain impact / effect / regulation-on-industry / policy-on-research
- preserve current public route response fields
- add internal query-trait extraction, for example:
  - `has_year`
  - `has_version_intent`
  - `has_effective_date_intent`
  - `has_trend_intent`
  - `is_policy_change`
  - `is_cross_domain_impact`

Design principle:

- do not overfit to one dataset
- improve signal quality without making `mixed` the default for every Chinese query

### 2. Budgeted Query Planning

Primary files:

- `skill/orchestrator/retrieval_plan.py`
- `skill/retrieval/engine.py`
- new helper module under `skill/orchestrator/` or `skill/retrieval/`
- `tests/test_retrieval_integration.py`
- new retrieval-planning regression tests if needed

Changes:

- introduce per-source budgeted query variants instead of a single raw query
- keep expansion small and route-aware

Planned behavior by route:

- `policy`
  - official term
  - revision / change / exemption / effective date variant when trait indicates
- `industry`
  - trend / forecast / shipment / share phrasing variant when trait indicates
- `academic`
  - paper / survey / benchmark / review lookup variant
- `mixed`
  - split into route-specific subqueries for primary and supplemental routes

Constraints:

- max 1 to 3 query variants per source step
- bounded by existing per-source and overall deadlines
- dedupe equivalent variants before execution
- avoid broad expansion when the query is already specific

Design principle:

- improve hidden-query recall without sacrificing latency discipline

### 3. Retrieval Ordering and Mixed Coverage

Primary files:

- `skill/retrieval/priority.py`
- `skill/retrieval/orchestrate.py`
- `tests/test_retrieval_integration.py`

Changes:

- improve query-match scoring for Chinese, bilingual, and year/entity-sensitive queries
- strengthen ranking on:
  - entity overlap
  - year/version/effective-date overlap
  - change/impact/trend wording alignment
- preserve domain-first ordering rules
- for mixed queries, ensure retained evidence favors cross-domain coverage rather than same-domain crowding

Specific mixed behavior:

- if both primary and supplemental routes produce usable evidence, the final retained evidence should include both
- primary-first ordering remains, but supplemental evidence must remain visible in top retained items

Design principle:

- make mixed-domain answers more complete without turning retrieval into an unbounded fusion system

### 4. Local-First Answering and Guarded Synthesis

Primary files:

- `skill/synthesis/orchestrate.py`
- possibly `skill/synthesis/prompt.py`
- `tests/test_answer_integration.py`
- `tests/test_answer_runtime_budget.py`

Changes:

- widen local fast-path coverage beyond the current narrow lookup patterns
- prefer local grounded answer assembly when evidence already satisfies:
  - strong query overlap
  - required route coverage
  - version/date requirements when relevant
  - citation sufficiency
- call MiniMax only when local evidence is not enough for a judge-readable answer

Post-generation guardrails:

- compare model output against local evidence-backed candidate
- fall back to local or insufficient-evidence response when generated output:
  - drops core entities
  - drops years, versions, or effective dates that matter to the query
  - weakens cross-domain coverage
  - provides weaker sources than the local candidate
  - cannot survive citation validation

Design principle:

- use the model as a narrow synthesis boundary, not the main reasoning engine

### 5. Quality-Gated Cache for Repeated Runs

Primary files:

- `skill/synthesis/orchestrate.py`
- `tests/test_answer_runtime_budget.py`
- `tests/test_api_runtime_benchmark.py`
- possibly benchmark tests

Changes:

- add a lightweight in-process cache keyed by:
  - normalized query
  - route identity
  - relevant query traits
  - pipeline version string
- cache only high-quality stable responses, for example:
  - grounded local fast-path responses
  - grounded responses that passed validation cleanly
- never cache:
  - retrieval failures
  - insufficient evidence responses
  - weak or degraded outputs

Design principle:

- exploit repeated benchmark structure for time and stability gains without polluting correctness

## Data Flow

### `/route`

- normalize query
- classify route
- derive internal query traits
- return the existing public route contract

### `/retrieve`

- build route-aware retrieval plan
- expand into small, budgeted query variants
- execute source steps under existing timeouts
- normalize, dedupe, score, and pack evidence
- preserve mixed-domain coverage where available

### `/answer`

- execute retrieval
- attempt stronger local fast path
- reject low-overlap evidence before generation
- invoke model only when needed
- validate generated citations
- compare generated output to stronger local evidence-backed candidate
- downgrade or fall back conservatively when unsupported
- publish runtime trace internally as before

## Failure Handling

The design keeps the current explicit failure-state philosophy.

- retrieval failure should remain distinct from insufficient evidence
- budget exhaustion should remain explicit
- weak evidence overlap should continue to short-circuit generation
- model-backend failures should not produce unsupported claims
- cache must never hide underlying retrieval or validation failures

## Testing Strategy

### Route Tests

- expand Chinese and bilingual route regressions
- cover policy-change, trend, benchmark, and cross-domain impact phrasing

### Retrieval Tests

- test query planning with bounded expansion
- test mixed-domain retention behavior
- test ranking improvements on entity/year/impact alignment

### Answer Tests

- test wider local fast paths
- test model fallback when generated output is weaker than local evidence
- test query-trait-sensitive guardrails for version/date/change queries
- test cache hit and miss behavior
- test cache does not store weak states

### Benchmark Tests

- keep locked benchmark regressions green
- preserve internal runtime telemetry publication
- preserve repeatability guarantees

## Success Criteria

This version is successful if it does all of the following:

- keeps the existing public submission structure intact
- keeps locked benchmark repeatability and strong latency behavior
- improves routing and retrieval behavior on Chinese and mixed-domain competition-style queries
- increases the number of competition-style queries that surface usable sources
- reduces unnecessary model calls on repeated and lookup-heavy workloads
- preserves the repo's strongest identity: explicit, grounded, stable answers

## Risks

Primary risks:

- route marker expansion may over-widen `mixed`
- query expansion may eat latency budget if not tightly capped
- mixed coverage enforcement may reduce the best single-domain result quality if made too rigid
- cache may create hidden coupling if keyed too loosely

Mitigations:

- add route regressions before broadening behavior
- keep query planning trait-driven and capped
- treat mixed coverage as a constraint only when both routes have credible evidence
- cache only stable grounded outputs with a versioned key

## Recommended Implementation Order

1. Route marker and query-trait enhancements
2. Budgeted query planning
3. Mixed-domain coverage and ranking refinement
4. Local-first answer widening and post-generation guardrails
5. Stable grounded-response cache
6. Locked benchmark verification
7. Competition-style evaluation verification

## Expected Outcome

The final result should be a competition submission that is meaningfully different from `WASC1`:

- `WASC1` as the broader-coverage submission
- `WASC` as the precision/stability submission with enough generalized recall to remain competitive on hidden tasks

That differentiation gives the two submissions distinct scoring paths instead of forcing them to compete for the same strengths.
