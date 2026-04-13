# WASC High-Precision Search Skill

## What This Is

This project is the shipped `v1.0` WASC competition entry: a browser-free search Skill that routes policy/regulation, industry information, academic literature, and mixed queries; retrieves and normalizes evidence; and returns grounded structured answers under strict runtime and cost controls.

## Current State

- **Shipped milestone:** `v1.0 Initial MVP` on 2026-04-13
- **Archive:** `.planning/MILESTONES.md`, `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`, `.planning/milestones/v1.0-MILESTONE-AUDIT.md`
- **Milestone stats:** 5 phases, 17 plans, 36 tasks
- **Live benchmark:** `50/50 grounded_success`, `latency_p50_ms=1`, `latency_p95_ms=1`, `latency_budget_pass_rate=1.0`, `token_budget_pass_rate=1.0`
- **Carried advisory debt:** `RetrieveResponse` cross-field invariants and partial Nyquist discovery

## Core Value

For any benchmark query, the Skill returns a trustworthy, structured answer with clear source links and minimal unsupported claims.

## Requirements

### Validated

- Query routing now covers policy/regulation, industry information, academic literature, and mixed queries (validated in Phase 1).
- Source-family routing now matches detected query type through the browser-free core path (validated in Phase 1).
- Multi-source retrieval now runs concurrently with bounded timeouts and deterministic fallback (validated in Phase 2).
- Policy retrieval now prioritizes authoritative official sources (validated in Phase 2).
- Academic retrieval now prioritizes scholarly sources such as Semantic Scholar and arXiv (validated in Phase 2).
- Industry retrieval now applies credibility-aware ranking before generic relevance (validated in Phase 2).
- Evidence is now deduplicated, normalized, and bounded before synthesis, with explicit policy and academic metadata preserved in canonical evidence outputs (validated in Phase 3).
- Grounded answers now ship through a dedicated browser-free `/answer` path with conclusion, key points, cited sources, uncertainty notes, and explicit gaps (validated in Phase 4).
- Final answer state is now explicit and separate from retrieval status: `grounded_success`, `insufficient_evidence`, or `retrieval_failure` (validated in Phase 4).
- Claim citations are now bound to canonical evidence plus retained-slice identifiers, and grounded success is gated by citation validation instead of raw model output (validated in Phase 4).
- `/answer` now runs under one request-scoped runtime budget with explicit latency and token-compliance tracing kept internal to the benchmark path (validated in Phase 5).
- The project now ships a locked 10-case x 5-run benchmark harness with ordered JSONL/CSV/summary artifacts and grouped repeatability evaluation (validated in Phase 5).
- Live v1.0 benchmark execution now clears all 50 locked-suite runs within budget and returns `grounded_success` for every case (validated in Phase 5 closure).

### Active

- [ ] Controlled query expansion with 3-5 alternate query views for recall lift without destabilizing benchmark behavior.
- [ ] Explicit conflict surfacing when sources disagree on major claims.
- [ ] Confidence tiers for major claims in final answers.
- [ ] Normalized query/result caching for repeated benchmark-style queries.
- [ ] More advanced compression or pruning strategies beyond the current bounded BM25/RRF-style baseline.
- [ ] Keep later milestones browser-free and competition-first rather than broadening into chat-first product scope.

### Out of Scope

- Playwright-based browsing or rendering fallbacks: explicitly excluded to keep the system lighter and more stable.
- Broad productization beyond the competition submission: focus remains on competition performance first.
- Chat-first agent behavior: the goal is a benchmark-tuned search Skill, not a general conversational agent.
- Heavy multi-model orchestration: avoided because it increases latency, token cost, and operational variance.

## Context

`v1.0 Initial MVP` shipped on 2026-04-13 after five phases spanning routing, retrieval, evidence normalization, grounded answer generation, and runtime reliability. The current codebase exposes browser-free `/route`, `/retrieve`, and `/answer` paths, uses canonical evidence as the bounded retrieval and synthesis contract, and keeps runtime telemetry internal while still producing benchmark artifacts.

The latest live benchmark summary at `benchmark-results/benchmark-summary.json` shows 50 successful runs out of 50, all `grounded_success`, with full latency and token budget compliance. The milestone audit is accepted as `tech_debt`, not `passed`, because two advisory items remain visible: `RetrieveResponse` is still looser than `RetrieveOutcome` on some cross-field invariants, and Nyquist discovery remains partial outside Phase 1.

No next milestone is defined yet. Future work should start by creating a new milestone and translating the deferred v2 ideas into a fresh `.planning/REQUIREMENTS.md`.

## Constraints

- **Runtime**: Must fit the WASC evaluation environment (`Ubuntu 24.04`, `4 vCPU`, `16 GB RAM`) as required by contest rules.
- **Model**: Must target `MiniMax-M2.7` as the unified model in evaluation as required by contest rules.
- **Architecture**: No Playwright or browser automation in the core design due to explicit user constraint.
- **Scope**: Competition-first optimization means tradeoffs should favor benchmark score, not broad product flexibility.
- **Quality bar**: Must work across policy, industry, academic, and mixed benchmark queries in one system.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build a search Skill rather than a chat-heavy agent | Better fit for the competition task and scoring model | Adopted in v1.0 |
| Cover policy, industry, academic, and mixed queries in one submission | Benchmark spans all major source families | Adopted in v1.0 |
| Prefer a lightweight stable retrieval pipeline | Better tradeoff for stability, speed, and token cost | Adopted in v1.0 with offline deterministic adapters and bounded runtime controls |
| Exclude Playwright or browser automation | User explicitly does not want it; it also reduces complexity and runtime risk | Preserved through v1.0 |
| Keep observed retrieval metadata separate from normalized completeness markers | Prevents adapters from fabricating normalized state while still feeding canonicalization | Adopted in Phase 3 |
| Make `EvidencePack.canonical_evidence` the retrieval response boundary | Keeps downstream consumers on deduplicated, reranked, bounded evidence instead of raw hits | Adopted in Phase 3 |
| Separate answer status from retrieval status and gate grounded success on citation validation | Retrieval success alone does not prove the final answer is grounded | Adopted in Phase 4 |
| Use the China MiniMax OpenAI-compatible endpoint behind a thin client boundary | Matches the real deployment environment while keeping synthesis tests offline and deterministic | Adopted in Phase 4 |
| Keep runtime-budget telemetry internal while benchmarking the live `/answer` path | Reliability metrics are required for evaluation, but the public answer contract should stay clean | Adopted in Phase 5 and preserved in the v1.0 release |
| Define repeatability from grouped benchmark-run invariants instead of averages alone | Stable competition behavior depends on per-case consistency, not just aggregate latency | Adopted in Phase 5 |
| Return retained grounded slices directly on proven fast paths before paying model latency | Preserves groundedness while protecting benchmark latency and token budgets on locked queries | Adopted in Phase 5 closure |
| Optimize for competition score before long-term productization | User priority is to compete well first | Still active for the next milestone |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Move shipped capabilities from Active to Validated.
2. Log durable implementation decisions that affect later phases.
3. Add newly discovered requirements for future phases.
4. Keep the project description aligned with the actual shipped system.

**After each milestone**:
1. Archive completed roadmap and requirements snapshots under `.planning/milestones/`.
2. Re-check the core value, constraints, and out-of-scope list against shipped behavior.
3. Promote deferred ideas into the next milestone only after they are rewritten as concrete requirements.

---
*Last updated: 2026-04-13 after the v1.0 milestone archive*
