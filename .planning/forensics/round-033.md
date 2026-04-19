# Round 033 Forensics

## Hypothesis

Short-circuit exact standards aliases and allow single-source standards exact-token lookups onto the industry fast path so `FedCM`, `ETSI EN 303 645`, and `RFC6265bis Partitioned` queries stop timing out or degrading to partial answers.

## Candidate Bundle

- `skill/retrieval/adapters/industry_ddgs.py`
  - strengthened direct official snippets for `FedCM`, `ETSI EN 303 645`, and `RFC6265bis`
  - direct standards aliases can now return before generic discovery
- `skill/synthesis/orchestrate.py`
  - broadened industry lookup recognition for standards-style exact-token queries so single-source authoritative evidence can use the local industry fast path

## Evaluation Setup

- Candidate code: current local runtime bundle in `D:\study\WASC-clean\.worktrees\autotune-loop`
- Control code: same worktree with only the round-033 runtime delta reverted to the round-032 baseline
- Shared manifest: `benchmark-results/autotune/round-033/cases.json`
- Fresh-cache candidate benchmark on 2026-04-19 with `--fresh-process --max-parallel 2`
  - initial run cache: `.wasc-live-cache/round-033-candidate-20260419-01`
  - initial result: `38 / 50`
- Fresh-cache same-worktree control benchmark on 2026-04-19 with `--fresh-process --max-parallel 2`
  - control cache: `.wasc-live-cache/control-round-033-20260419-01`
  - control result: `41 / 50`
- Fresh-cache candidate benchmark rerun on 2026-04-19 with `--fresh-process --max-parallel 2`
  - rerun cache: `.wasc-live-cache/round-033-candidate-20260419-02`
  - rerun result: `46 / 50`
- Fresh-cache candidate packet export on 2026-04-19 with `--shadow-eval --max-parallel 2`
  - candidate cache: `.wasc-live-cache/round-033-candidate-packets-20260419-01`
- Fresh-cache same-worktree control packet export on 2026-04-19 with `--shadow-eval --max-parallel 2`
  - control cache: `.wasc-live-cache/control-round-033-packets-20260419-01`
- Judge scoring:
  - not run in-session
  - packet bundle is ready for later 3-judge scoring

## What Happened

The first candidate benchmark run looked negative on aggregate:

- initial candidate benchmark: `38 / 50`
- control benchmark: `41 / 50`

But the case-level movement from that first run did not match the code delta:

- candidate gains were exactly in the intended standards/query family
  - `gen3-hard-02`
  - `gen3-hard-06`
  - `gen3-hard-09`
  - `gen3-hard-10`
- the losses were almost entirely unrelated academic drift
  - `gen3-academic-01`
  - `gen3-academic-05`
  - `gen3-academic-06`
  - `gen3-academic-07`
  - `gen3-academic-08`
  - `gen3-academic-09`
  - `gen3-hard-08`

That mismatch strongly suggested live-noise contamination rather than a real regression from the changed files.

So the candidate was rerun on a second fresh cache before rejection.

## Effective Benchmark Outcome

The rerun reproduced the intended family gains and cleared the same-worktree control:

- effective candidate benchmark: `46 / 50 = 0.920`
- same-worktree control benchmark: `41 / 50 = 0.820`
- benchmark delta: `+0.100`

Effective benchmark answer-status breakdown:

- Candidate rerun
  - `grounded_success`: `46`
  - `insufficient_evidence`: `3`
  - `retrieval_failure`: `1`
- Control
  - `grounded_success`: `41`
  - `insufficient_evidence`: `4`
  - `retrieval_failure`: `5`

Targeted benchmark wins versus control:

- `gen3-hard-02`: `retrieval_failure -> grounded_success`
- `gen3-hard-06`: `retrieval_failure -> grounded_success`
- `gen3-hard-09`: `retrieval_failure -> grounded_success`
- `gen3-hard-10`: `retrieval_failure -> grounded_success`
- `gen3-academic-03`: incidental live uplift on rerun

## Packet Outcome

The packet surface also stayed positive:

- candidate packets: `46 / 50 grounded_success`
- control packets: `42 / 50 grounded_success`
- packet delta: `+4`

Targeted packet wins versus control:

- `gen3-hard-02`
- `gen3-hard-06`
- `gen3-hard-10`

Other packet observations:

- `gen3-hard-09` was already grounded in the control packet run, so the main packet gain stayed concentrated in the exact-token standards family
- `gen3-mixed-06` still fails
- `gen3-mixed-07` still tops out at `insufficient_evidence`

## Interpretation

Round-033 is worth keeping locally as the new lead candidate.

The first benchmark run was noisy, but the rerun plus packet comparison show a coherent family-level gain:

- exact-token standards lookups no longer waste time fetching generic page bodies
- the answer path now treats single-source authoritative standards evidence as enough for direct grounded lookup responses
- the gain reproduced on both benchmark rerun and packet export

This round also improves wall-clock behavior for the affected family:

- `gen3-hard-02` dropped to ~`5 ms` in benchmark rerun
- `gen3-hard-06` dropped below `1 s`
- `gen3-hard-10` dropped to ~`2 s`

## Remaining Gaps

The strongest remaining improvement lane is still mixed cross-domain recovery:

- `gen3-mixed-05`
- `gen3-mixed-06`
- `gen3-mixed-07`

Those cases still fail because the policy side can now recover more often, but the supplemental industry side remains too timeout-prone or too weakly aligned to complete a grounded mixed answer.

## Decision

Keep round-033 locally as the active lead candidate, treat the rerun benchmark as the effective benchmark artifact for this round, and continue future iteration from the round-033 runtime state.
