# Phase 1: Query Routing & Core Path Guardrails - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers deterministic query typing and source-family routing for benchmark questions through a browser-free core execution path. It covers how incoming queries are classified as policy/regulation, industry information, academic literature, or mixed; how that classification maps to source families; and what routing metadata is exposed in the structured response. It does not add multi-source retrieval orchestration, evidence reranking, answer synthesis, or browser-based fallbacks.

</domain>

<decisions>
## Implementation Decisions

### Mixed-query routing
- **D-01:** Mixed queries default to a **primary route + one supplemental route**, not a single-route-only path and not three-way parallel fan-out.
- **D-02:** The supplemental route is enabled only when the query shows **explicit cross-domain intent** (for example, policy impact on industry, or research-versus-regulation comparisons), not merely because confidence is low.

### Classification policy
- **D-03:** Phase 1 should use a **rule-first deterministic classifier**, not model-first classification and not a hybrid model fallback in the initial scope.
- **D-04:** For single-label conflicts, default precedence is **Policy > Academic > Industry** unless the query is explicitly cross-domain enough to become mixed.

### Routing observability
- **D-05:** The Phase 1 response should expose **route label + selected source families** to make routing directly observable.
- **D-06:** Routing observability should live in **structured response fields**, not just internal logs.

### Low-confidence handling
- **D-07:** Low-confidence classification should **escalate to mixed**, not default to industry and not fail closed with an insufficient-route state in the main path.
- **D-08:** Very short or underspecified queries should follow the same rule: **upgrade to mixed** rather than asking for clarification or refusing the route.

### Claude's Discretion
- Exact keyword/entity rule set and scoring thresholds inside the rule-first classifier
- Concrete source-family identifiers and structured response field names
- Internal debug metadata and log shape, as long as the user-facing contract remains `route label + source families`

</decisions>

<specifics>
## Specific Ideas

- Keep the routing layer competition-first: deterministic, cheap, and easy to validate.
- Mixed handling should be conservative on cost: one main route plus one supplement, not full fan-out.
- Observability should be built into the response contract so routing behavior can be tested directly.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contest and project constraints
- `比赛.txt` — Contest source of truth for deliverables, runtime environment, scoring rubric, and benchmark framing across policy, industry, and academic queries.
- `.planning/PROJECT.md` — Core product framing, browser-free constraint, competition-first scope, and cross-domain coverage requirement.
- `.planning/REQUIREMENTS.md` — Phase-mapped requirements `ROUT-01`, `ROUT-02`, and `ROUT-03`.
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and boundary relative to later phases.

### Routing architecture and Phase 1 design
- `claude/需求.md` — End-to-end pipeline proposal with intent classification, route-specific sources, and lightweight core-path assumptions.
- `chatgpt/WASC_信源路由与基线策略.md` — Detailed source-routing rules by policy, industry, academic, and mixed query type, including preferred and deprioritized source families.
- `chatgpt/WASC_4月挑战赛参赛方案讨论稿.md` — Benchmark-first framing for a “query router + result compressor” system and route-by-query-type design logic.
- `.planning/research/ARCHITECTURE.md` — Planned module decomposition, rule-first intent classifier, route planner, and mixed-query flow notes.

### Failure modes and guardrails
- `.planning/research/PITFALLS.md` — Key routing failure modes, especially treating all query classes as one route and over-introducing browser-heavy paths.
- `.planning/research/FEATURES.md` — Priority rationale for query typing, source routing, and lightweight stable execution.
- `.planning/STATE.md` — Current focus note that Phase 1 should stay route-first and browser-free.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — the repository is currently a planning workspace with no implemented application code, routing modules, or test harness.

### Established Patterns
- Planning artifacts are phase-driven under `.planning/` and should be treated as the current source of implementation truth.
- The current architecture direction is Python-first, rule-first, and browser-free in the core path.
- Later phases are intentionally separated: Phase 1 stops at classification plus source-family routing rather than full retrieval or answer synthesis.

### Integration Points
- Future implementation should connect an input query validator/classifier to a route planner and a structured response contract that returns route metadata.
- Phase 1 output must become the contract boundary consumed by Phase 2 retrieval adapters and source-priority logic.

</code_context>

<deferred>
## Deferred Ideas

- Browser-based fallback or Playwright-assisted retrieval — explicitly out of Phase 1 and out of the core path.
- Low-confidence `insufficient-route` refusal state — not selected for the main Phase 1 path.
- Hybrid classifier with model fallback — deferred unless rule-first routing proves insufficient in later validation.

</deferred>

---

*Phase: 01-query-routing-core-path-guardrails*
*Context gathered: 2026-04-08*
