# 2026-04-17 Judge Packet Scoring Design

## Goal
Add a local evaluation workflow that runs one round of WASC queries, captures the answer plus supporting evidence into compact packet files, and then lets Codex-side scoring agents evaluate those packets with no extra repo context.

## Why This Round Exists
The official rules weight completeness, accuracy, operability, stability, and usability more heavily than any internal route label. The repo currently has runtime telemetry and benchmark traces, but it does not preserve the answer/evidence bundle needed for higher-level scoring.

The user also clarified the desired judging method:

- do not use `MiniMax` as the scoring model
- do not wire the judge into runtime code paths
- run one round first
- then spawn a few Codex agents with only the answer materials
- do not mix in unrelated repo context

That changes the implementation target. The right deliverable is not an in-repo LLM judge backend. The right deliverable is a packet-export path that makes session-time subagent scoring possible and clean.

## Chosen Direction
Build a packet-export workflow with two layers:

1. `export_judge_packets(...)`
   - runs the selected case manifest through `/retrieve` and `/answer`
   - writes one compact JSON packet per case
2. session-time subagent scoring
   - use `spawn_agent(..., fork_context=false)`
   - pass only the packet text and a rubric for one dimension
   - collect scores for completeness, accuracy, and usability separately

The repo will only own layer 1. Layer 2 stays in the Codex session so the judge model is decoupled from the submission codebase.

## Packet Shape
Each packet should include only the materials a scoring agent actually needs:

- `case_id`
- `query`
- `retrieve`
  - `status`
  - `failure_reason`
  - `gaps`
  - `canonical_evidence`
  - `evidence_clipped`
  - `evidence_pruned`
- `answer`
  - `answer_status`
  - `retrieval_status`
  - `conclusion`
  - `key_points`
  - `sources`
  - `uncertainty_notes`
  - `gaps`
- `runtime`
  - `elapsed_ms`
  - `retrieval_elapsed_ms`
  - `synthesis_elapsed_ms`
  - `provider_total_tokens`
  - `failure_reason`
  - `retrieval_trace`

No repo docs, no benchmark history, no handoff narrative, and no classifier rationale should be embedded in the packet.

## Scope
This first rollout should:

- support the existing benchmark manifest format with `case_id` and `query`
- write one packet file per case
- write an index file for the round
- stay separate from the public `/answer` contract

This first rollout should not:

- implement automatic in-repo judge scoring
- change benchmark success criteria
- change retrieval or answer behavior
- depend on `MiniMax` for judging

## Expected Outcome
After one exported round, the session can spawn several scoring agents that each see only:

- the packet content
- a narrow scoring rubric

That gives a cleaner and more controllable qualitative evaluation loop than reusing internal route labels or benchmark-only success counts.
