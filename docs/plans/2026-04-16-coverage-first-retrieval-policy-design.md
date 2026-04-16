# 2026-04-16 Coverage-First Retrieval Policy Design

## Goal
Raise hidden-style generalization by changing how the system decides to spend retrieval budget after primary evidence arrives. The target is not a new intent taxonomy. The target is a more reliable evidence-acquisition policy that delays commitment until the system has either enough coverage or a clear reason to stop.

## Why This Round Exists
Recent artifact-backed results point to the same pattern:

- [generated-hidden-like-r1-v47-generalization benchmark-summary.json](D:/study/WASC-clean/benchmark-results/generated-hidden-like-r1-v47-generalization/benchmark-summary.json) stayed at `26 / 50`, with failures dominated by `timeout`.
- [generated-hidden-like-academic-r1-v1 benchmark-summary.json](D:/study/WASC-clean/benchmark-results/generated-hidden-like-academic-r1-v1/benchmark-summary.json) reached `9 / 10`, which means academic is no longer the main strategic drag.
- [generated-hidden-like-mixed-r1-v3 benchmark-summary.json](D:/study/WASC-clean/benchmark-results/generated-hidden-like-mixed-r1-v3/benchmark-summary.json) stayed at `0 / 10`, and the failures were all retrieval-side.
- [post-primary-probe benchmark-summary.json](D:/study/WASC-clean/benchmark-results/post-primary-probe-verify-36abc537e124/benchmark-summary.json) also stayed at `0 / 6`, showing that a single local probe is too narrow to fix the larger policy problem.

The user also explicitly rejected:

- case-by-case correction
- keyword or marker expansion as the primary strategy
- reopening heavier first-hop `mixed`

That changes the problem statement. The remaining work is not "classify hidden mixed cases better." It is "spend retrieval budget in a way that improves evidence coverage before the system commits to a narrow answer path."

## What Is Not Retained
The design must not regress into the approaches that are already disproven:

- No heavier first-hop `mixed` routing.
- No new four-class or trainable first-hop router.
- No business-vocabulary marker sprawl.
- No single-case patches framed as general rules.
- No hidden RSS-only finalization.

These are established by [HANDOFF.md](D:/study/WASC-clean/HANDOFF.md) and [.continue-here.md](D:/study/WASC-clean/.planning/.continue-here.md).

## External Pattern Match
The broader retrieval literature is converging on policy and timing, not taxonomy:

- Adaptive-RAG routes by retrieval complexity and can choose no retrieval, single-shot retrieval, or iterative retrieval instead of forcing one path for every query.
  - Source: https://arxiv.org/abs/2403.14403
- IRCoT shows that retrieval should depend on what has already been derived, not just on the original query.
  - Source: https://arxiv.org/abs/2212.10509
- Self-RAG and FLARE both treat retrieval as on-demand and critique-driven rather than fixed upfront.
  - Sources: https://openreview.net/forum?id=jbNjgmE0OP, https://aclanthology.org/2023.emnlp-main.495/
- DRAGIN explicitly separates "when to retrieve" from "what to retrieve" and optimizes both against real-time information needs.
  - Source: https://arxiv.org/html/2403.10081v1
- PAR2-RAG is the closest architectural analogue for this repo's current failure mode: build coverage first, commit later, then deepen only one promising branch.
  - Source: https://arxiv.org/html/2603.29085v1

GraphRAG is lower fit here. It is better matched to offline graph construction over stable corpora than to low-latency live-web evidence acquisition.
  - Source: https://raw.githubusercontent.com/microsoft/graphrag/main/README.md

## Chosen Direction
Use a hybrid of:

- coverage-first frontier building
- adaptive stop/deepen control

The system should:

1. Keep the current primary route stable.
2. Let primary retrieval try to win on its own.
3. If primary evidence is strong but still incomplete, spend a small bounded budget to build a cheap evidence frontier.
4. Only after frontier coverage exists should the system decide whether to:
   - stop with a grounded answer
   - deepen one promising branch
   - stop with `insufficient_evidence`

This preserves the user's desired shift in abstraction:

- from intent labels to evidence state
- from first-hop fan-out to post-primary budget control
- from sample corrections to structural retrieval policy

## Core Design

### Stage 1: Stable Primary Acquisition
Do not change the current primary route planner for this round.

The existing path remains:

- classify query
- build primary-first retrieval plan
- run retrieval
- normalize, score, dedupe, and pack evidence

This protects retained wins in policy, academic, and industry.

### Stage 2: Cheap Coverage Frontier
If Stage 1 returns strong primary evidence but the system still cannot safely ground the answer, it should build a small frontier instead of immediately committing to one extra local probe.

The frontier is a ranked list of bounded supplemental probes. Each probe is:

- `target_route`
- `source_id`
- `probe_query`
- `reason_code`
- `timeout_seconds`

The frontier is not open-ended search. It is a micro-budget breadth step.

#### Frontier Constraints
- Build the frontier only when primary retrieval succeeded.
- Do not build it when primary retrieval already has gaps or hard failure signals.
- Do not build it when remaining request budget is too low.
- Cap the frontier to at most two candidate probes in v1.
- Each candidate probe gets one strongest source and a short timeout.
- The frontier should be generated from query variants and evidence novelty, not from benchmark-case tables.

#### Initial Scope
The policy abstraction should be generic, but the first implementation should activate only for the `policy <-> industry` complement pair.

Reason:

- that is where the artifact-backed scoring gap is
- it keeps blast radius small
- it tests the architecture on the most relevant lane without reopening full-route taxonomy work

Academic does not need this in the first rollout because the isolated academic slice already improved materially.

### Stage 3: Evidence Sufficiency Controller
After the frontier is built, the system should make a bounded decision:

- `STOP_GROUNDED`
- `DEEPEN_ONE_BRANCH`
- `STOP_INSUFFICIENT`

This controller should remain deterministic and local in v1. It should not use another model call.

#### Controller Inputs
- query content terms
- primary evidence strength
- whether route diversity now exists
- alignment score of frontier hits
- remaining retrieval and synthesis budget

#### Controller Rules
- Stop grounded when:
  - the existing local mixed fast-path becomes valid, or
  - one primary record plus one supplemental record now give enough aligned support.
- Deepen one branch when:
  - one frontier branch clearly dominates on alignment and novelty, and
  - enough budget remains for one more bounded retrieval step.
- Stop insufficient when:
  - no branch produces useful evidence, or
  - budget is too low to deepen safely.

This keeps the policy close to PAR2-RAG's "coverage first, commitment late" principle without importing a full agentic multi-hop loop.

## Why This Is Better Than The Current Post-Primary Probe
The current experimental post-primary probe is still too local:

- it assumes a single branch
- it assumes a single source is enough
- it does not separate frontier building from commitment
- it does not expose an explicit stop/deepen controller

That is why it could be structurally correct but still fail to retain live gains.

The new design changes the unit of decision from "do one more probe" to:

- "build a tiny frontier"
- "pick the best branch only if evidence says it is worth deepening"

## Implementation Shape

### New Module
Create a dedicated policy module instead of adding more branching to the already large answer orchestrator:

- `skill/synthesis/retrieval_policy.py`

Responsibilities:

- frontier candidate representation
- frontier candidate generation
- budget gating
- sufficiency decision
- branch ranking helpers

### Existing Files To Modify
- `skill/config/retrieval.py`
  - add frontier-specific constants
- `skill/synthesis/orchestrate.py`
  - call the policy layer after local fast-path miss and before model synthesis
  - record internal retrieval-trace stages for frontier and deepen steps
- `tests/test_answer_runtime_budget.py`
  - add policy-level regressions

Optional, only if needed:

- `skill/retrieval/orchestrate.py`
  - only if a small helper is needed to shape frontier results consistently

### Trace Strategy
Do not change the public `/answer` or `/retrieve` schema.

Use the existing internal runtime trace path and add distinct benchmark-only stage names such as:

- `coverage_frontier_probe`
- `coverage_frontier_deepen`

This keeps observability without introducing a public contract change.

## Expected Effects

### Positive
- fewer mixed failures caused by immediate commitment after one-sided retrieval
- less dependence on first-hop `mixed`
- better use of remaining retrieval budget
- more interpretable traces for hidden-style failures

### Accepted Tradeoffs
- some additional local orchestration complexity
- slightly more retrieval work in a small subset of cases
- initial rollout only addresses the strongest cross-domain lane, not every route pair

These tradeoffs are acceptable because the system is already paying timeout cost without converting it into coverage.

## Success Criteria
A successful first rollout should show all of the following:

1. No regression in the existing targeted regression suite.
2. No reopening of heavier first-hop `mixed`.
3. At least some mixed cases move from:
   - `retrieval_failure -> insufficient_evidence`, or
   - `insufficient_evidence -> grounded_success`
4. Fresh-process artifacts show shorter and more explainable mixed traces.
5. Timeout pressure does not worsen materially in the mixed slice or smoke gate.

## Validation Plan
Verification must stay artifact-backed and fresh-process:

- targeted unit/regression tests around frontier gating and deepen decisions
- the existing retained regression suite from handoff
- fresh-process mixed slice validation
- fresh-process smoke gate validation

Required runtime settings:

- `WASC_RETRIEVAL_MODE=live`
- `WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED=0`
- unique `WASC_LIVE_CACHE_DIR`

## Non-Goals
- no new first-hop router
- no full ReAct or IRCoT style answer-time multi-hop loop
- no new search backend
- no LLM-based controller in v1
- no benchmark-case allowlists
- no attempt to solve every route pair in one rollout

## Decision
Proceed with a bounded `coverage-first + adaptive stop/deepen` implementation. Treat the current post-primary single-probe experiment as useful evidence, but not as the retained architecture.
