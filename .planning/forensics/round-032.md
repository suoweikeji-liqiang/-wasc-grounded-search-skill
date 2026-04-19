# Round 032 Forensics

## Hypothesis

Rebuild the strongest previously positive structural gains on top of current `HEAD`:

- restore policy-first direct-source coverage and policy fast-path behavior
- fix filing-vs-policy ambiguity for company disclosure queries
- add standards and CBAM official aliases without broadening retrieval fan-out

## Evaluation Setup

- Candidate code: current local runtime bundle in `D:\study\WASC-clean\.worktrees\autotune-loop`
  - `skill/orchestrator/intent.py`
  - `skill/retrieval/adapters/industry_ddgs.py`
  - `skill/retrieval/adapters/policy_official_registry.py`
  - `skill/retrieval/engine.py`
  - `skill/retrieval/live/clients/policy_eur_lex.py`
  - `skill/retrieval/live/clients/policy_us_agencies.py`
  - `skill/synthesis/orchestrate.py`
- Control code: same worktree with only those runtime files restored to `HEAD`
- Shared manifest: `benchmark-results/autotune/round-032/cases.json`
- Fresh-cache candidate benchmark on 2026-04-19 with `--fresh-process --max-parallel 2`
  - candidate cache: `.wasc-live-cache/round-032-candidate-20260419-01`
- Fresh-cache same-worktree control benchmark on 2026-04-19 with `--fresh-process --max-parallel 2`
  - control cache: `.wasc-live-cache/control-round-032-20260419-01`
- Fresh-cache candidate packet export on 2026-04-19 with `--shadow-eval --max-parallel 2`
  - candidate cache: `.wasc-live-cache/round-032-candidate-packets-20260419-01`
- Fresh-cache same-worktree control packet export on 2026-04-19 with `--shadow-eval --max-parallel 2`
  - control cache: `.wasc-live-cache/control-round-032-packets-20260419-01`
- Judge scoring:
  - not run in-session
  - packet bundle is ready, but the normal workflow expects 3 independent no-context judges

## Benchmark Outcome

This round reproduced as a large positive same-day gain:

- candidate benchmark: `44 / 50 = 0.880`
- control benchmark: `34 / 50 = 0.680`
- benchmark delta: `+0.200`

Additional runtime movement:

- candidate latency budget pass rate: `0.86`
- control latency budget pass rate: `0.70`
- candidate timeouts: `5`
- control timeouts: `12`

Answer-status breakdown:

- Candidate
  - `grounded_success`: `44`
  - `insufficient_evidence`: `2`
  - `retrieval_failure`: `4`
- Control
  - `grounded_success`: `34`
  - `insufficient_evidence`: `6`
  - `retrieval_failure`: `10`

## Packet Outcome

The packet surface also stayed strongly positive on fresh cache:

- candidate packets: `42 / 50 grounded_success`
- control packets: `34 / 50 grounded_success`
- packet delta: `+8`

Packet improvement families included:

- filing ambiguity recovery
  - `gen3-industry-10`
- mixed policy-update recovery
  - `gen3-mixed-02`
  - `gen3-mixed-03`
  - `gen3-mixed-07` improved from `retrieval_failure` to `insufficient_evidence`
- policy official-text recovery
  - `gen3-hard-05`
- broader packet stability
  - candidate removed several control-side retrieval failures while keeping the existing strong policy and filing wins

## What Actually Helped

The observed uplift came from a coherent structural bundle rather than one narrow case fix:

- filing-heavy company disclosure questions no longer fall into mixed policy handling just because they contain generic words like `official` or `obligations`
- policy-first mixed queries regained fast direct-source wins for FTC click-to-cancel and FDA section `524B`
- single-source authoritative policy evidence can use the local policy fast path more often
- CBAM official coverage now includes the authorised declarant / embedded-emissions regulation lane
- standards queries pick up more official aliases before generic discovery noise
- policy direct-family early-stop behavior reduced unnecessary mixed-query retry churn

## Residual Gaps

The remaining failures still cluster in a few recognizable families:

- cross-domain mixed tails
  - `gen3-mixed-06`
  - `gen3-mixed-07` still lacks strong enough supplemental industry evidence
- standards exact-token tails
  - `gen3-hard-02`
  - `gen3-hard-06`
  - `gen3-hard-10`
- one filing-comparison tail
  - `gen3-hard-09`

The proxy smoke check on `tests/fixtures/benchmark_hidden_style_smoke_cases.json` stayed modest at `2 / 8`, which means this round is a large improvement on the main hidden-style holdout, but not evidence that the broader cross-lingual/generalization problem is fully solved.

## Interpretation

Round-032 is the first local candidate in this session that clears both same-day gates decisively:

- benchmark improved by ten grounded cases versus control
- packet export improved by eight grounded cases versus control
- the improvement came from route selection, direct-source coverage, and fast-path behavior that map to query families, not one-off answer wording changes

That makes the round worth keeping locally as the current lead candidate and worth sending to judge scoring when 3 independent judges are available.

## Decision

Keep the round-032 runtime bundle locally as the active lead candidate, mark judge scoring as pending, and continue future iterations from this candidate state rather than from `HEAD`.
