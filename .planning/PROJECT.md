# WASC High-Precision Search Skill

## What This Is

This project is a WASC competition entry: a search Skill focused on low-cost, high-precision retrieval across policy/regulation, industry information, and academic literature queries. It is designed to produce structured, source-backed answers that score well on the WASC rubric, with an emphasis on accuracy, completeness, stability, and practical usability under the contest runtime constraints.

## Core Value

For any benchmark query, the Skill returns a trustworthy, structured answer with clear source links and minimal unsupported claims.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] The Skill covers all three benchmark query classes: policy/regulation, industry information, and academic literature.
- [ ] The Skill prefers lightweight, stable retrieval and processing paths over heavy browser-driven tooling.
- [ ] The Skill produces structured outputs optimized for judging: conclusion, key points, source links, and uncertainty markers where evidence is incomplete.
- [ ] The Skill avoids Playwright and similar browser automation in the core path.
- [ ] The project is optimized for WASC scoring rather than general-purpose product breadth.

### Out of Scope

- Playwright-based browsing or rendering fallbacks — explicitly excluded to keep the system lighter and more stable.
- Broad productization beyond the competition submission — focus is on competition performance first.
- Chat-first agent behavior — the goal is a benchmark-tuned search Skill, not a general conversational agent.

## Context

The repository is being shaped around the WASC April challenge for low-cost, high-precision search. The contest evaluates a fixed benchmark under a constrained environment and rewards strong information accuracy and completeness, plus good response time, stability, token efficiency, and usability. Existing repository documents converge on the same broad direction: classify the query, route to source-appropriate retrieval, perform local reranking/compression, then generate a structured grounded answer.

The intended project should cover policy, industry, and academic questions in one submission rather than specializing in only one domain. The user does not want Playwright in the solution and is not optimizing for long-term product breadth right now; the main goal is to build something that can compete well.

## Constraints

- **Runtime**: Must fit the WASC evaluation environment (`Ubuntu 24.04`, `4 vCPU`, `16 GB RAM`) — required by contest rules.
- **Model**: Must target `MiniMax-M2.7` as the unified model in evaluation — required by contest rules.
- **Architecture**: No Playwright/browser automation in the core design — explicit user constraint.
- **Scope**: Competition-first optimization — tradeoffs should favor benchmark score, not broad product flexibility.
- **Quality bar**: Must work across policy, industry, and academic queries in one system — explicit product scope.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build a search Skill rather than a chat-heavy agent | Better fit for the competition task and scoring model | — Pending |
| Cover policy, industry, and academic queries in one submission | Benchmark spans all three areas | — Pending |
| Prefer a lightweight stable retrieval pipeline | Better tradeoff for stability, speed, and token cost | — Pending |
| Exclude Playwright/browser automation | User explicitly does not want it; also reduces complexity and runtime risk | — Pending |
| Optimize for competition score before long-term productization | User priority is to compete well first | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-07 after initialization*
