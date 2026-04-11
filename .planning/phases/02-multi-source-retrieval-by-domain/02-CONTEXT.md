# Phase 2: Multi-Source Retrieval by Domain - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers domain-aware multi-source retrieval on top of the Phase 1 routing contract. It covers which concrete retrieval sources each route uses, how concurrent retrieval is budgeted and bounded, how deterministic fallback behaves when sources fail or return nothing, and how domain-specific source priority is applied before later evidence normalization work. It does not add browser-based retrieval to the core path, full evidence deduplication/reranking, or answer synthesis.

</domain>

<decisions>
## Implementation Decisions

### Source lineup
- **D-01:** The first Phase 2 retrieval release should use a **stable lightweight source mix**, not a broad or API-heavy provider set.
- **D-02:** **Policy** retrieval starts with **official/authority-first sources plus a constrained official-domain web fallback**, not pure-official only and not official plus unrestricted general web in parallel.
- **D-03:** **Academic** retrieval starts with **Semantic Scholar + arXiv** as the main retrieval pair, not a larger multi-provider scholarly stack in the first pass.
- **D-04:** **Industry** retrieval starts with **ddgs-based candidate gathering plus credibility-layered filtering** (`company official > industry association > trusted news > general web`), not a commercial-search-first approach.
- **D-05:** For **mixed** queries, the **primary route runs its full first-wave source set** while the **supplemental route contributes one strongest supporting source only**, not a symmetric full-source fan-out.

### Concurrency and deadlines
- **D-06:** Retrieval should use a **hard-budget concurrency model**, not a completeness-first waiting strategy.
- **D-07:** Each retrieval source should run with an **approximately 3-second per-source timeout**.
- **D-08:** The retrieval stage should also have a **fixed overall deadline**; it should not rely only on per-source timeouts.
- **D-09:** For a given query, sources in the current retrieval plan should be **launched together** under a **global concurrency cap**, not source-by-source staging.
- **D-10:** When the retrieval deadline is hit, the system should **immediately converge on returned results and drop unfinished slow sources**, not grant extra grace time by default.

### Degradation and fallback
- **D-11:** Phase 2 should use a **deterministic degradation chain**, not adaptive retry loops or open-ended recovery.
- **D-12:** A source that returns **no hits** should be treated as a **soft failure** that triggers the normal backup path, not a query-rewrite retry in the Phase 2 main path.
- **D-13:** A **429 / rate-limit** response should cause the system to **switch directly to the predefined backup source**, not wait through a longer backoff inside the core path.
- **D-14:** If retrieval still cannot assemble enough usable results, the system should return a **structured retrieval failure / gaps outcome**, not a bare API error and not a heavy final fallback path.

### Domain-aware source priority
- **D-15:** Phase 2 ranking/selection should be **rule-prioritized by domain**, not relevance-first across all routes.
- **D-16:** For **policy** queries, **official / regulatory / standards originals outrank secondary interpretation results absolutely** when both are available.
- **D-17:** For **academic** queries, only **scholarly sources** (Semantic Scholar / arXiv class) should enter the main candidate set in the first release; ordinary web pages do not join the main academic candidate pool.
- **D-18:** For **industry** queries, the first-pass priority order is **company official > industry association > trusted news > general web**, with recency and relevance applied within a credibility tier.
- **D-19:** For **mixed** queries, the **primary route remains dominant** in candidate priority and the supplemental route acts as supporting evidence / supporting perspective, not an equal co-primary branch.

### Claude's Discretion
- Exact provider names and adapter boundaries inside each approved source category
- Concrete values for the global concurrency semaphore and overall retrieval-stage deadline
- Internal error codes, telemetry fields, and failure-reason enums as long as they preserve the structured failure/gaps outcome
- The exact scoring formula used within an already approved domain priority tier

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contest and product constraints
- `比赛.txt` — Contest source of truth for runtime constraints, deliverable structure, and scoring priorities.
- `.planning/PROJECT.md` — Competition-first framing, browser-free core-path constraint, and cross-domain search goal.
- `.planning/REQUIREMENTS.md` — Phase-mapped retrieval requirements `RETR-01` through `RETR-05`.
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria, and dependency on Phase 1.
- `.planning/STATE.md` — Current workflow position and the project-level note to prioritize domain-aware concurrent retrieval before later optimization.

### Prior phase contract
- `.planning/phases/01-query-routing-core-path-guardrails/01-CONTEXT.md` — Locked routing decisions that Phase 2 must inherit: browser-free core path, mixed=`primary + one supplemental`, and observable structured route metadata.
- `skill/api/schema.py` — Current route response contract consumed by retrieval planning.
- `skill/config/routes.py` — Current route-to-source-family mapping from Phase 1.
- `skill/orchestrator/planner.py` — Existing route planning boundary that Phase 2 extends into concrete retrieval planning.

### Retrieval architecture and design direction
- `claude/需求.md` — End-to-end routed retrieval proposal with async multi-source search, per-source timeout guidance, and domain source examples.
- `chatgpt/WASC_4月挑战赛参赛方案讨论稿.md` — Benchmark-first argument for route-aware source selection, layered trust, fallback, and light-path retrieval.
- `gemini/WASC搜索挑战赛落地方案.md` — Lean async fetch baseline emphasizing strict timeout control and lightweight local denoising.
- `.planning/research/ARCHITECTURE.md` — Standard architecture for async fan-out retrieval, deadline-driven orchestration, and deterministic degradation FSM.
- `.planning/research/FEATURES.md` — MVP priorities for multi-source retrieval, fallback behavior, and structured evidence-oriented outputs.
- `.planning/research/PITFALLS.md` — Retrieval-specific failure modes around source trust, version drift, duplicate academic records, and unstable fallback behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skill/api/schema.py` — Existing Pydantic route request/response models provide the contract boundary Phase 2 should consume rather than redesign.
- `skill/config/routes.py` — Current immutable route precedence and route-to-source-family table can anchor concrete source selection.
- `skill/orchestrator/intent.py` — Deterministic classifier already produces `primary_route`, `supplemental_route`, and `route_label`, which retrieval should use directly.
- `skill/orchestrator/planner.py` — Current route planner already merges primary and supplemental source families for mixed queries; Phase 2 can extend this planner into retrieval-ready source plans.
- `skill/api/entry.py` — Existing FastAPI route endpoint gives a natural integration point for retrieval orchestration in later phases or expanded API contracts.
- `tests/test_route_contracts.py` — Existing contract-style regression tests establish a pattern for Phase 2 retrieval matrix and fallback regressions.

### Established Patterns
- The implemented codebase is currently **Python-first, schema-first, and deterministic**, matching the planning docs.
- Existing modules use **immutable constants** and **frozen dataclasses**, so Phase 2 should preserve immutable configuration and result objects.
- Phase 1 deliberately stopped at **route planning and source-family selection**, which makes Phase 2 the first place to introduce concrete providers, async retrieval, and failure-state handling.
- The repository already favors **small focused modules** (`intent`, `planner`, `normalize`, `schema`) rather than a single orchestrator file.

### Integration Points
- Phase 2 should connect the existing route contract to a **retrieval planner / runtime controller / source adapter layer** like the structure proposed in `.planning/research/ARCHITECTURE.md`.
- Retrieval output should preserve enough structure to feed Phase 3 evidence normalization without reclassifying the query.
- Structured retrieval failure / gaps outcomes should become the contract boundary that later answer-generation phases can distinguish from successful grounded retrieval.

</code_context>

<specifics>
## Specific Ideas

- Keep the first release intentionally narrow: stable, lightweight providers beat broader provider coverage.
- Mixed-query handling should stay cost-conservative: the primary route does the main retrieval work and the supplemental route only adds one strongest supporting source.
- Retrieval should be deadline-driven rather than completeness-driven to protect repeatability under contest constraints.
- Domain trust rules should be explicit and testable rather than hidden inside a generic relevance score.

</specifics>

<deferred>
## Deferred Ideas

- Commercial-search-first provider strategy for industry retrieval — deferred in favor of a lighter ddgs-based baseline.
- Larger scholarly source mesh (for example Crossref/OpenAlex in the first pass) — deferred until the lean Semantic Scholar + arXiv baseline is validated.
- Query rewrite retries on empty hits in the Phase 2 main path — deferred to later optimization work.
- Symmetric full-source fan-out for mixed queries — explicitly deferred because it conflicts with the Phase 1 cost guardrail.
- Heavy final-fallback browsing path — deferred and outside the browser-free core path.

</deferred>

---

*Phase: 02-multi-source-retrieval-by-domain*
*Context gathered: 2026-04-11*
