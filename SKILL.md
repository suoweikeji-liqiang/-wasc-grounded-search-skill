# SKILL: WASC High-Precision Search Skill

## Purpose

This Skill solves low-cost, high-precision search tasks by routing a query to the right source family, retrieving bounded evidence, and returning a structured grounded answer with traceable citations.

It is built for WASC-style evaluation across:

- policy and regulation queries
- industry information queries
- academic literature queries
- mixed-domain benchmark queries

## Input

Input contract:

```json
{"query":"user query text"}
```

The public API accepts a single trimmed non-empty `query` string up to 2000 characters.

## Output

The final answer surface is `POST /answer`.

Output characteristics:

- explicit `answer_status`
- explicit `retrieval_status`
- structured `conclusion`
- citation-backed `key_points`
- deduplicated `sources`
- `uncertainty_notes`
- `gaps`

Possible final answer states:

- `grounded_success`
- `insufficient_evidence`
- `retrieval_failure`

## Processing Flow

1. Classify query intent and route family.
2. Build a domain-aware retrieval plan.
3. Execute concurrent retrieval with bounded fallback behavior.
4. Normalize and deduplicate evidence into canonical bounded records.
5. Generate a structured answer draft.
6. Validate citations against retained evidence slices.
7. Return a grounded answer only if citation checks pass.

## Public Surfaces

- `POST /route`
- `POST /retrieve`
- `POST /answer`
- `scripts/route_query.py`
- `scripts/run_benchmark.py`

## Design Constraints

- Browser automation is disabled in the core path.
- Runtime budgets are enforced on `/answer`.
- Benchmark telemetry stays internal and is not leaked in the public answer schema.
- The Skill is competition-first, not a general-purpose chat agent.

## What This Skill Does Well

- keeps retrieval and answer generation grounded to explicit evidence
- preserves structured output shape for evaluation
- supports repeatable local benchmark execution
- handles policy, academic, industry, and mixed queries in one pipeline

## What This Skill Does Not Do

- browse arbitrary pages with Playwright or Selenium
- act as a multi-step autonomous research agent
- expose internal latency or token traces in the public answer response
- optimize for broad consumer-product UX over competition scoring

## Verification Snapshot

- full test suite: `172 passed`
- answer-focused suite: `33 passed`
- latest live benchmark: `50/50 grounded_success`

## Primary Files

- `skill/api/entry.py`
- `skill/api/schema.py`
- `skill/retrieval/orchestrate.py`
- `skill/evidence/*`
- `skill/synthesis/*`
- `skill/benchmark/*`

