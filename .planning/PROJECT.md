# WASC High-Precision Search Skill

## What This Is

This project is a WASC competition entry: a search Skill focused on low-cost, high-precision retrieval across policy/regulation, industry information, and academic literature queries. It is designed to produce structured, source-backed answers that score well on the WASC rubric, with an emphasis on accuracy, completeness, stability, and practical usability under the contest runtime constraints.

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
- Benchmark telemetry remains internal while the public answer contract stays clean and repeatable under deterministic offline benchmark execution (validated in Phase 5).

### Active

- [ ] The Skill keeps browser automation out of the main path across later phases as well.
- [ ] The project remains optimized for WASC scoring rather than general-purpose product breadth.

### Out of Scope

- Playwright-based browsing or rendering fallbacks: explicitly excluded to keep the system lighter and more stable.
- Broad productization beyond the competition submission: focus is on competition performance first.
- Chat-first agent behavior: the goal is a benchmark-tuned search Skill, not a general conversational agent.

## Context

The repository is being shaped around the WASC April challenge for low-cost, high-precision search. The contest evaluates a fixed benchmark under a constrained environment and rewards strong information accuracy and completeness, plus good response time, stability, token efficiency, and usability. Existing repository documents converge on the same broad direction: classify the query, route to source-appropriate retrieval, perform local reranking/compression, then generate a structured grounded answer.

Phases 1 through 5 are now complete: the project can classify benchmark queries, expose source-family routing without browser automation, execute deterministic multi-source retrieval, return domain-prioritized retrieval results, hand off deduplicated, metadata-rich, top-K bounded evidence sets for synthesis, produce grounded structured answers through the `/answer` path, and run repeatable benchmark evaluations with explicit runtime-budget governance and internal compliance telemetry.

## Constraints

- **Runtime**: Must fit the WASC evaluation environment (`Ubuntu 24.04`, `4 vCPU`, `16 GB RAM`) as required by contest rules.
- **Model**: Must target `MiniMax-M2.7` as the unified model in evaluation as required by contest rules.
- **Architecture**: No Playwright/browser automation in the core design due to explicit user constraint.
- **Scope**: Competition-first optimization means tradeoffs should favor benchmark score, not broad product flexibility.
- **Quality bar**: Must work across policy, industry, and academic queries in one system.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build a search Skill rather than a chat-heavy agent | Better fit for the competition task and scoring model | Adopted in Phases 1-2 |
| Cover policy, industry, and academic queries in one submission | Benchmark spans all three areas | Routing and retrieval paths implemented in Phases 1-2 |
| Prefer a lightweight stable retrieval pipeline | Better tradeoff for stability, speed, and token cost | Adopted with offline deterministic adapters and bounded runtime controls |
| Exclude Playwright/browser automation | User explicitly does not want it; also reduces complexity and runtime risk | Preserved through Phases 1-2 |
| Keep observed retrieval metadata separate from normalized completeness markers | Prevents adapters from fabricating normalized state while still feeding canonicalization | Adopted in Phase 3 |
| Make `EvidencePack.canonical_evidence` the retrieval response boundary | Ensures downstream consumers see deduplicated, reranked, bounded evidence instead of raw prioritized hits | Adopted in Phase 3 |
| Separate answer status from retrieval status and gate grounded success on citation validation | Retrieval success alone does not prove the final answer is grounded | Adopted in Phase 4 |
| Use the China MiniMax OpenAI-compatible endpoint behind a thin client boundary | Matches the real deployment environment while keeping synthesis tests offline and deterministic | Adopted in Phase 4 |
| Keep runtime-budget telemetry internal while benchmarking the live `/answer` path | Reliability metrics are required for evaluation, but the public API contract should stay clean | Adopted in Phase 5 |
| Define repeatability from grouped benchmark-run invariants instead of averages alone | Stable competition behavior depends on per-case consistency, not just aggregate latency | Adopted in Phase 5 |
| Optimize for competition score before long-term productization | User priority is to compete well first | Still active and guiding later phases |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Move shipped capabilities from Active to Validated.
2. Log durable implementation decisions that affect later phases.
3. Add newly discovered requirements for future phases.
4. Keep the project description aligned with the actual shipped system.

**After each milestone**:
1. Review all sections.
2. Re-check the core value and out-of-scope list.
3. Update context with the latest system state and remaining roadmap.

---
*Last updated: 2026-04-12 after Phase 5*
