---
phase: 02-multi-source-retrieval-by-domain
plan: 03
subsystem: retrieval
tags: [pytest, fastapi, retrieval-priority, domain-routing]
requires:
  - phase: 02-multi-source-retrieval-by-domain
    provides: retrieval runtime control and fallback FSM from 02-02
provides:
  - Domain-constrained adapter implementations for policy, academic, and industry retrieval sources
  - D-15 rule-prioritized ordering via `prioritize_hits(...)` for policy/academic/industry/mixed routes
  - Runtime/API retrieval pipeline enforcing `run_retrieval -> prioritize_hits -> response shaping`
affects: [phase-03-evidence-normalization, ranking, api-retrieval]
tech-stack:
  added: [none]
  patterns: [tdd-red-green, domain-first-priority, route-dominant-mixed-ordering]
key-files:
  created:
    - skill/retrieval/adapters/policy_official_registry.py
    - skill/retrieval/adapters/policy_official_web_allowlist.py
    - skill/retrieval/adapters/academic_semantic_scholar.py
    - skill/retrieval/adapters/academic_arxiv.py
    - skill/retrieval/adapters/industry_ddgs.py
    - skill/retrieval/priority.py
    - skill/retrieval/orchestrate.py
    - tests/test_retrieval_integration.py
  modified:
    - skill/api/entry.py
    - tests/test_domain_priority.py
key-decisions:
  - "Policy fallback adapter filters by explicit official-domain allowlist before creating hits."
  - "Academic main candidate filtering is enforced in priority layer to keep only Semantic Scholar/arXiv-class sources."
  - "Industry ordering uses explicit credibility tiers first, then recency/relevance only within each tier."
patterns-established:
  - "Mandatory runtime ordering pipeline: retrieve raw hits, prioritize by domain rules, then shape API contract output."
  - "Mixed-route retrieval keeps primary route candidates ahead of supplemental evidence."
requirements-completed: [RETR-03, RETR-04, RETR-05]
duration: 6min
completed: 2026-04-12
---

# Phase 2 Plan 03: Multi-Source Retrieval by Domain Summary

**Domain-scoped adapters and a rule-first prioritization engine now drive retrieval responses through a strict runtime/API orchestration path.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-12T00:45:36+08:00
- **Completed:** 2026-04-12T00:51:56+08:00
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added deterministic async adapters for policy registry, policy allowlist fallback, Semantic Scholar, arXiv, and ddgs industry retrieval.
- Implemented `prioritize_hits(...)` with D-15 rule-priority semantics and domain-specific constraints for policy, academic, industry, and mixed routing.
- Added `execute_retrieval_pipeline(...)` and wired FastAPI `/retrieve` to guarantee all runtime hits pass through domain-priority before response shaping.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Implement constrained domain adapter tests** - `1be183f` (`test`)
2. **Task 1 (GREEN): Implement constrained domain adapters** - `8e811f1` (`feat`)
3. **Task 2 (RED): Add priority/integration/API failing tests** - `6b3bffe` (`test`)
4. **Task 2 (GREEN): Implement priority + orchestration + API wiring** - `db3c13c` (`feat`)

## Verification Commands

- `pytest tests/test_domain_priority.py -k "allowlist or scholarly or industry_tier" -q` (pass)
- `pytest tests/test_domain_priority.py tests/test_retrieval_integration.py -q` (pass)
- `rg -n "credibility_tier|SOURCE_CREDIBILITY_TIERS|academic_semantic_scholar|academic_arxiv|allowlist" skill/retrieval/adapters tests/test_domain_priority.py` (matches found)
- `rg -n "prioritize_hits\(|execute_retrieval_pipeline|run_retrieval|D-15|domain-first|rule-prioritized" skill/retrieval/priority.py skill/retrieval/orchestrate.py skill/api/entry.py tests/test_retrieval_integration.py tests/test_domain_priority.py` (matches found)
- `python -c "from skill.retrieval.orchestrate import execute_retrieval_pipeline; from skill.retrieval.priority import prioritize_hits; print('integration-import-ok')"` (prints `integration-import-ok`)

## Files Created/Modified

- `skill/retrieval/adapters/policy_official_registry.py` - official policy registry adapter with deterministic fixtures.
- `skill/retrieval/adapters/policy_official_web_allowlist.py` - fallback policy adapter enforcing official-domain allowlist filtering before hit creation.
- `skill/retrieval/adapters/academic_semantic_scholar.py` - Semantic Scholar scholarly adapter.
- `skill/retrieval/adapters/academic_arxiv.py` - arXiv scholarly adapter.
- `skill/retrieval/adapters/industry_ddgs.py` - ddgs adapter with deterministic credibility-tier annotation.
- `skill/retrieval/priority.py` - domain-first D-15 ranking rules and mixed-route dominance ordering.
- `skill/retrieval/orchestrate.py` - runtime pipeline enforcing retrieval-to-priority-to-response sequence.
- `skill/api/entry.py` - `/retrieve` endpoint wiring through retrieval plan and orchestration.
- `tests/test_domain_priority.py` - domain rule-priority and adapter-constraint regressions.
- `tests/test_retrieval_integration.py` - runtime call-sequence and API wiring regressions.

## Decisions Made

- Used deterministic fixture-backed adapter `search()` implementations for stable test behavior without network dependence.
- Kept policy allowlist enforcement at adapter boundary and academic filtering at priority boundary for explicit trust controls.
- Implemented mixed-route ordering as primary-route prioritized hits followed by supplemental-route hits to satisfy D-19.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Retrieval output is now domain-ordered and stable for evidence normalization/reranking follow-up work.
- API/runtime integration path can no longer bypass priority logic for retrieval responses.

---
*Phase: 02-multi-source-retrieval-by-domain*
*Completed: 2026-04-12*

## Self-Check: PASSED

- Found summary file: `.planning/phases/02-multi-source-retrieval-by-domain/02-03-SUMMARY.md`
- Found commits: `1be183f`, `8e811f1`, `6b3bffe`, `db3c13c`
