# 2026-04-16 Academic Fallback Narrowing Design

## Goal
Improve live hidden-style success rate by shortening academic source execution paths. Prioritize success rate and deadline discipline over long-tail recall. Changes must be structural and generalizable, not tuned to a single benchmark prompt.

## Confirmed Root Cause
Fresh-process smoke and retrieval-trace inspection showed that academic failures were not caused only by missing sources. Two structural issues were confirmed:

1. Multiple academic query variants could collapse to the same upstream ASCII query through `academic_upstream_query()`, causing repeated equivalent requests within one source budget.
2. Academic adapters still contained internal fallback chains that extended beyond cheap structured metadata lookups into slower discovery behavior, making source-level timeouts opaque and consuming budget that should have gone to source-to-source fallback.

The first issue was already addressed by engine-level upstream-query deduplication for academic variants. This design covers the second issue.

## Chosen Approach
Adopt a stricter adapter boundary for academic retrieval.

### `academic_semantic_scholar`
Keep only:
- Semantic Scholar
- OpenAlex

Remove:
- `search_multi_engine(... site:doi.org)` fallback

### `academic_arxiv`
Keep only:
- arXiv
- Europe PMC

Remove:
- `search_multi_engine(... site:arxiv.org)` fallback

### `academic_asta_mcp`
No change in this round.

### `engine`
No new planner behavior in this round.
Keep:
- staged academic fallback (`semantic_scholar -> arxiv -> asta`)
- academic variant prioritization
- academic upstream-query dedupe

## Why This Should Generalize
This change does not add query-specific keywords, new backend routing, or benchmark-case exceptions. It changes the execution shape:
- metadata adapters stay metadata-focused
- source-to-source fallback remains in the planner/engine
- slow web discovery is no longer hidden inside a metadata source budget

That makes retrieval traces easier to interpret and should improve deadline reliability across hidden-style sets, especially for mixed-language academic prompts.

## Data Flow After Change
1. Engine builds academic variants.
2. Engine prioritizes academic variants and dedupes by normalized upstream query.
3. `academic_semantic_scholar` runs:
   - Semantic Scholar
   - OpenAlex if needed
   - stop
4. If still unresolved, engine falls back to `academic_arxiv`.
5. `academic_arxiv` runs:
   - arXiv
   - Europe PMC if needed
   - stop
6. If still unresolved, engine falls back to `academic_asta_mcp`.

## Expected Effects
Positive:
- fewer source-level timeouts caused by hidden tail work
- faster transfer from Semantic Scholar miss to arXiv fallback
- better mixed-route academic support because supplemental academic evidence should arrive sooner
- cleaner retrieval traces with more honest attribution

Accepted tradeoff:
- some long-tail academic recovery that previously depended on discovery fallback may be lost

This is acceptable for this round because success-rate stability was explicitly chosen over long-tail recall.

## Files In Scope
Implementation:
- `skill/retrieval/adapters/academic_semantic_scholar.py`
- `skill/retrieval/adapters/academic_arxiv.py`

Tests:
- `tests/test_academic_live_adapters.py`
- existing coverage in `tests/test_retrieval_query_variants.py`
- existing coverage in `tests/test_retrieval_fallback.py`
- existing coverage in `tests/test_retrieval_concurrency.py`

## Test Plan
Add or update tests to prove:
1. Semantic Scholar adapter does not call `search_multi_engine` after Semantic Scholar + OpenAlex miss/failure.
2. arXiv adapter does not call `search_multi_engine` after arXiv + Europe PMC miss/failure.
3. engine-level academic upstream-query dedupe remains intact.
4. source-to-source academic fallback contract still holds.

Then verify with:
- targeted pytest for academic adapters and retrieval fallback/concurrency tests
- fresh-process smoke gate with:
  - `WASC_RETRIEVAL_MODE=live`
  - `WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED=0`
  - unique `WASC_LIVE_CACHE_DIR`

## Success Criteria
A good result for this round is:
1. academic adapters no longer hide web discovery tail work
2. smoke traces for academic/mixed are shorter and more interpretable
3. at least one academic or mixed smoke case improves structurally
4. no regression in the explicit academic fallback contract

## Non-Goals
- no classifier changes
- no new search backends
- no industry work unless a new blocker appears later
- no query-specific marker expansion
- no timeout retuning beyond what already exists
