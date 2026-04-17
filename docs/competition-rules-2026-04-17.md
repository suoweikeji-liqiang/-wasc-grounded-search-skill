# Competition Rules Snapshot (2026-04-17)

This note normalizes the latest official rules recorded in [`../比赛.txt`](../比赛.txt) into repo-facing engineering implications.

## Official Constraints

- Evaluation window: Beijing time `10:00 - 12:00`
- Runtime environment: `4 vCPU`, `16 GB RAM`, `Linux kernel > 5.14`, `Ubuntu 24.04`
- Unified model: `MiniMax-M2.7`
- Evaluation set: `10` fixed keyword tasks across policy/regulation, industry information, and academic literature
- Stability regime: each of the `10` tasks is repeated `5` times, for `50` total runs

## Official Scoring

- Request time: `15`
- Tokens: `10`
- Information completeness: `20`
- Information accuracy: `20`
- Operability: `10`
- Stability: `15`
- Usability: `10`

Latency is bucketed by the average response time across the `10` tasks:

- `<= 10s`: `15`
- `10s - 30s`: `12`
- `30s - 60s`: `8`
- `> 60s`: `4`
- timeout or execution failure: `0`

Tie-breakers are ordered as:

1. information accuracy
2. token consumption
3. stability

## Strategic Reading For This Repo

The repo's recent search direction was partially misframed.

- There is no official evidence that `8s` is a hard competition cutoff.
- An internal route label such as `mixed` is not itself a scoring target.
- The primary optimization target should be end-to-end score under the seven official dimensions, not route-label agreement on self-authored fixtures.

## What This Changes

- Treat outright failures and timeouts as a first-order problem because they zero both latency and operability while also damaging stability.
- Treat answer completeness and answer accuracy as co-primary with latency, not secondary polish.
- Judge benchmark progress by grounded success, source support, and repeatability before judging it by internal route taxonomy.

## Current Misalignment To Watch

`mixed` is overloaded in the current classifier and is carrying several different failure types:

- explicit cross-domain queries
- short queries
- low-signal queries
- ambiguity between domains
- score ties

That makes "improve mixed" an unstable objective. For analysis and future benchmark slicing, those cases should be separated conceptually into at least:

- true cross-domain
- underspecified
- ambiguous
- low-signal

There is also an environment-fit risk against the official Ubuntu runtime:

- root docs and submission docs are still PowerShell-first
- local helper scripts such as `scripts/run_wasc_on_wasc1_eval.py` and `scripts/compare_impls.py` still contain hard-coded `D:\...` paths
- this is separate from retrieval quality and can directly hurt operability and usability if not cleaned before submission

## Practical Next Focus

- Reduce policy and industry timeout-heavy failures in fresh-process live runs.
- Improve completeness only after primary evidence is real, not by route-time fan-out inflation.
- Add evaluation views that are closer to the official scorecard: response-time buckets, success rate, repeated-run stability, and answer-quality checks with source support.
- Audit Linux portability and strip Windows-only assumptions from submission-facing scripts and setup docs.
