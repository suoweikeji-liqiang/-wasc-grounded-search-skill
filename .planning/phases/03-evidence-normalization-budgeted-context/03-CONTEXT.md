# Phase 3: Evidence Normalization & Budgeted Context - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers post-retrieval evidence normalization for the existing domain-aware retrieval pipeline. It covers canonical evidence shaping, domain-specific duplicate collapse, metadata completeness rules for policy and academic evidence, and bounded top-K context packing ahead of answer synthesis. It does not add final answer generation, claim writing, or benchmark reliability harness work.

</domain>

<decisions>
## Implementation Decisions

### Evidence unit shape
- **D-01:** The canonical evidence unit should be **document + retained evidence slices**, not document-only and not slice-only.
- **D-02:** Phase 3 should keep both the **raw retrieval record** and a **normalized canonical record** internally.
- **D-03:** Each canonical document should retain **at most 2 evidence slices** by default.
- **D-04:** The normalized evidence object should optimize first for **downstream traceability**, not implementation minimalism and not maximum recall at any cost.

### Duplicate collapse policy
- **D-05:** **Policy** duplicates should collapse by **document identity plus version/date-aware canonical matching**, not by URL-only and not by title-similarity alone.
- **D-06:** **Academic** duplicates should use canonical key priority **DOI > arXiv ID > title + first author + year**.
- **D-07:** **Industry** content should use **conservative near-duplicate collapse** based on same-domain plus high title/snippet similarity, not event-level merging.
- **D-08:** When duplicate records contain complementary metadata, the system should **merge the supplemental metadata into the canonical record** rather than discard it.

### Policy metadata completeness
- **D-09:** A policy record missing `version` may still enter the evidence pack if the source is otherwise credible, but it must be explicitly marked `version_missing`.
- **D-10:** `publication_date` and `effective_date` must remain separate fields; if `effective_date` is unknown, the normalized record should say so explicitly rather than collapsing both into one generic date.
- **D-11:** Missing policy `jurisdiction` should not cause automatic rejection when other signals are strong, but the record must be labeled `jurisdiction_inferred` or `jurisdiction_unknown` instead of silently defaulting to national scope.
- **D-12:** The minimum bar for policy evidence entering the pack is **authority + at least one date field**. `jurisdiction` and `version` may be missing only if the normalized record marks that incompleteness explicitly.

### Academic canonicalization
- **D-13:** When a preprint and a formally published paper match, the **published version becomes the canonical record**.
- **D-14:** Non-canonical variants should be preserved as **linked variants** under the canonical academic record, not discarded and not kept as full independent evidence entries.
- **D-15:** Academic evidence should expose an explicit evidence level such as **`peer_reviewed`, `preprint`, `survey_or_review`, or `metadata_only`**.
- **D-16:** Heuristic academic merges are allowed when DOI is unavailable, but they must carry a **`canonical_match_confidence=heuristic`** style marker rather than pretending to be a strong identifier match.

### Budgeted context packing
- **D-17:** Evidence packing should use a **hard token budget plus a top-K ceiling**, not fixed-K alone and not token-only without a record cap.
- **D-18:** Packing should use **one global budget**, but for mixed queries the supplemental route should receive a **small protected minimum share** so it can still contribute supporting evidence while the primary route remains dominant.
- **D-19:** When over budget, the system should **prune low-scoring slices before dropping whole documents**.
- **D-20:** Full budget accounting should remain internally available, while external response surfaces should expose only whether clipping/pruning occurred rather than detailed internal budget telemetry.

### the agent's Discretion
- Exact normalized field names and Python model boundaries, as long as the distinction between raw records, canonical records, linked variants, and retained slices remains explicit.
- Exact duplicate-similarity thresholds for industry near-duplicate collapse and heuristic academic matching.
- Exact token-budget values, slice scoring formula, and clip-indicator field name, as long as hard-budget enforcement and supplemental-route minimum share are preserved.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contest and project constraints
- `比赛.txt` - Contest framing, runtime constraints, and judging priorities that make evidence quality and bounded context non-negotiable.
- `.planning/PROJECT.md` - Competition-first direction, browser-free constraint, and project-level value of trustworthy source-backed answers.
- `.planning/REQUIREMENTS.md` - Phase-mapped requirements `EVID-01` through `EVID-04`.
- `.planning/ROADMAP.md` - Phase 3 goal, success criteria, and boundary relative to retrieval and answer-generation phases.
- `.planning/STATE.md` - Current milestone state and carry-forward concerns from Phase 2 that affect Phase 3 planning.

### Prior phase contract
- `.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md` - Locked retrieval decisions that Phase 3 must inherit: hard budgets, domain-first priority, mixed primary-route dominance, and structured failure/gaps behavior.
- `.planning/phases/01-query-routing-core-path-guardrails/01-CONTEXT.md` - Original route contract and mixed-query rules that still constrain supplemental evidence handling in Phase 3.

### Research guidance for normalization and packing
- `.planning/research/ARCHITECTURE.md` - Recommended pipeline placement for canonicalization, dedupe, evidence scoring, and token pruning.
- `.planning/research/PITFALLS.md` - Known failure modes around policy version/jurisdiction gaps, academic preprint/published duplication, and token explosion from overlong context.
- `.planning/research/SUMMARY.md` - Project-level summary that explicitly calls for evidence schema, canonical IDs, and hard context budgets.

### Current code contracts to extend
- `skill/retrieval/models.py` - Current retrieval hit contract that Phase 3 normalization will extend beyond `source_id/title/url/snippet/credibility_tier`.
- `skill/api/schema.py` - Current API response models and retrieval output envelope that will eventually need to coexist with normalized evidence outputs.
- `skill/retrieval/engine.py` - Retrieval runtime boundary that currently returns flat hit lists before any canonicalization or top-K pruning.
- `skill/retrieval/orchestrate.py` - Current orchestration point where retrieval results are prioritized and shaped for API output.
- `skill/retrieval/priority.py` - Existing domain-priority ordering logic that Phase 3 evidence scoring must build on rather than replace.
- `skill/orchestrator/retrieval_plan.py` - Route plan contract and budget parameters that Phase 3 evidence packing must respect.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skill/retrieval/models.py`: Existing `RetrievalHit` and `SourceExecutionResult` contracts provide the current raw evidence boundary and should be extended, not replaced blindly.
- `skill/api/schema.py`: Existing `RetrieveResultItem` and `RetrieveResponse` models give a stable external contract surface while normalized evidence stays internal or is phased into later APIs.
- `skill/retrieval/priority.py`: Current domain-first ordering already encodes trust/route precedence and can feed Phase 3 scoring before packing.
- `skill/retrieval/engine.py`: The retrieval engine already centralizes first-wave results, fallback outcomes, and gaps, making it the natural upstream source for normalization.
- `skill/retrieval/orchestrate.py`: This is the current handoff from raw retrieval outcome to shaped response and is a likely insertion point for a normalization/packing stage.
- `skill/orchestrator/retrieval_plan.py`: The retrieval plan already carries deadline and concurrency settings that define the upstream budget envelope for Phase 3.

### Established Patterns
- The codebase is still **Python-first, schema-first, and deterministic**, using frozen dataclasses and Pydantic models instead of loose dict-shaped state.
- Retrieval currently produces **flat hit lists**, so Phase 3 is the first phase that should introduce canonical document records, linked variants, and retained slices.
- Domain-specific behavior is already encoded explicitly in code and tests, which means normalization and dedupe rules should also stay explicit and testable by domain.
- Mixed-query behavior is already **primary-route dominant**, so evidence packing should preserve that asymmetry while guaranteeing a small supplemental contribution.

### Integration Points
- Insert normalization after retrieval execution/domain-priority ordering and before any future Phase 4 answer synthesis.
- Preserve enough raw provenance from retrieval hits so that later claim-to-source binding can point back to a specific retained slice.
- Keep normalized evidence compatible with current retrieval status/failure semantics so later phases can distinguish successful evidence packs from partial or failed retrieval states.

</code_context>

<specifics>
## Specific Ideas

- Preserve evidence traceability over the simplest possible implementation.
- Missing metadata must be explicit rather than silently inferred or dropped without signal.
- Mixed-query evidence should stay primary-route dominant, but the supplemental route must not be starved completely during packing.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 03-evidence-normalization-budgeted-context*
*Context gathered: 2026-04-12*
