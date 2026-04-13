# Implementation Comparison Design

## Goal

Compare `D:\study\WASC` and `D:\study\WASC1` against the same locked 10-case benchmark baseline so both implementations can be evaluated with one report.

## Chosen Approach

Use the current `WASC` Phase 5 benchmark manifest as the shared baseline:

- dataset: `tests/fixtures/benchmark_phase5_cases.json`
- implementation A: current `WASC` FastAPI `/answer` path
- implementation B: `WASC1` `skill.main.run_query(query)` path

## Why This Approach

- `WASC` already uses this manifest for the current shipped reliability benchmark.
- `WASC1` has its own 12-case evaluation script, but its pass criteria are heuristic and not aligned with the current `WASC` locked benchmark.
- Reusing the shipped 10-case manifest avoids comparing two different task sets.

## Comparison Scope

Per case, collect:

- query
- expected route
- predicted route for each implementation
- elapsed latency in milliseconds
- source count
- uncertainty count where available
- answer status where available
- summary or conclusion preview

Aggregate:

- route accuracy
- average and p95 latency
- average source count
- uncertainty rate
- grounded-success rate for `WASC`
- non-empty-answer rate for `WASC1`

## Normalization Rules

### WASC

- execute through the existing FastAPI app and `/answer`
- use `app.state.last_runtime_trace` for latency and route telemetry
- read `answer_status` and `sources` from the public response

### WASC1

- import `skill.main.run_query`
- import `skill.router.classify_query`
- measure wall-clock latency around `run_query(query)`
- infer source count from returned `sources`
- infer uncertainty count from returned `uncertainties`

## Output Artifacts

Write a machine-readable report under the current repo:

- `benchmark-results/impl-comparison-summary.json`

Optional console table:

- one row per case
- one aggregate summary block

## Constraints

- do not modify `D:\study\WASC1`
- do not change the locked 10-case manifest
- keep the comparison script self-contained inside `D:\study\WASC`
- leave unrelated dirty files untouched

## Risks

- `WASC1` may require live keys and network for default adapters
- the two implementations expose different response contracts, so only shared metrics should be compared directly
- `WASC` has explicit answer-state semantics while `WASC1` does not

## Approved Direction

- compare on the `WASC` 10-case locked baseline
- build a single comparison script in `D:\study\WASC`
- run it and report both implementations side by side
