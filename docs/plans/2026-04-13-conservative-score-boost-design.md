# Conservative Score Boost Design

**Date:** 2026-04-13

**Goal:** Improve competition-facing answer quality metrics for this repository without changing retrieval architecture, route decisions, or citation guardrails.

## Scope

- Tighten local fast-path conclusion wording so it covers query-critical terms more directly.
- Reduce non-informative uncertainty notes only when evidence is already strong and grounded.
- Add targeted `2026`-style regressions that protect the score-focused behavior.

## Non-Goals

- No retrieval adapter rewrites.
- No route or mixed-domain planner changes.
- No relaxed citation validation.
- No model prompt expansion that increases latency or instability.

## Approaches Considered

### 1. Template-only keyword stuffing

Change only conclusion strings to include more benchmark terms.

Pros:
- Lowest implementation risk.

Cons:
- Barely affects uncertainty rate.
- Can become brittle and obviously benchmark-shaped.

### 2. Uncertainty-only suppression

Keep answer text mostly unchanged and report fewer uncertainty notes.

Pros:
- Directly improves uncertainty-heavy outputs.

Cons:
- Risks hiding genuine evidence/runtime limits.
- Does not materially improve keyword coverage.

### 3. Recommended: fast-path answer shaping plus stricter uncertainty precision

Adjust only local grounded answer shaping and uncertainty derivation for strong-evidence cases, then lock behavior with focused regressions.

Pros:
- Real quality improvement instead of metric-only gaming.
- Preserves current routing, retrieval, and guardrail stability.
- Directly targets the two remaining soft metrics: keyword coverage and unnecessary uncertainty.

Cons:
- Requires careful test design to avoid weakening existing evidence warnings.

## Design

### Answer shaping

- Keep the existing local fast paths for policy, industry, academic, and mixed answers.
- Upgrade conclusion construction so the first sentence echoes high-signal query terms already supported by evidence:
  - policy: version/date/change/exemption wording
  - industry: trend/forecast/shipment/share wording
  - academic: paper/research/benchmark wording
  - mixed: policy or regulation term plus industry-side impact term
- Prefer terms that already appear in the query or retained evidence instead of injecting new vocabulary.

### Uncertainty precision

- Keep uncertainty notes for real user-visible limitations:
  - retrieval gaps
  - citation validation issues
  - clipped/pruned evidence when there is no strong multi-source local grounding
  - policy metadata incompleteness when the answer depends on that metadata
  - academic heuristic merge notes when only heuristic linkage supports the answer
- Suppress uncertainty notes only when:
  - retrieval succeeded
  - there are no gaps
  - local fast path has strong direct support from the retained evidence set
  - the flagged condition does not materially weaken the answer being returned

### Testing

- Add focused regressions first for:
  - `2026` industry forecast/trend conclusion coverage
  - academic benchmark/paper wording in local conclusions
  - mixed conclusions retaining both cross-domain scoring terms
  - uncertainty suppression only for strong local grounded cases
- Keep existing guardrail and uncertainty contract tests green.

## Success Criteria

- Full test suite remains green.
- Competition eval stays at `12/12`.
- Average keyword coverage improves or stays high.
- Uncertainty rate drops without introducing false confidence in weak-evidence cases.
