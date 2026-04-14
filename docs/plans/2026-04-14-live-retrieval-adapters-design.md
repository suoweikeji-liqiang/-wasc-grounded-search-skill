# Live Retrieval Adapters Design

**Date:** 2026-04-14

**Goal:** Replace fixture-backed retrieval adapters with live network-backed adapters that preserve the current grounded `/route` -> `/retrieve` -> `/answer` pipeline and improve hidden-query performance on unknown competition inputs.

## Scope

- Keep the existing routing, retrieval orchestration, evidence normalization, citation validation, and answer-state logic intact.
- Replace the default runtime behavior of the current five adapters with live implementations:
  - `policy_official_registry`
  - `policy_official_web_allowlist_fallback`
  - `academic_semantic_scholar`
  - `academic_arxiv`
  - `industry_ddgs`
- Add headless discovery and fetch capabilities that can use multiple general search engines for discovery where appropriate.
- Preserve deterministic fixture paths for offline tests and local fallback behavior.

## Non-Goals

- No MCP server, admin dashboard, browser pool autoscaling, or other platform-style infrastructure work.
- No changes to the public `/route`, `/retrieve`, or `/answer` contracts.
- No relaxation of citation gating or evidence-quality guardrails.
- No broad rewrite of the scoring, canonicalization, or answer synthesis pipeline.

## Approaches Considered

### 1. Minimal inline live calls

Patch each adapter in place with direct HTTP and browser logic.

Pros:
- Fastest path to first live result.

Cons:
- Couples network logic, parsing, and adapter policy together.
- Hard to extend, test, or tune after the initial change.

### 2. Recommended: layered live adapter architecture

Keep the current adapter boundaries, but add shared live clients, parsers, and cache helpers underneath them.

Pros:
- Reuses the current retrieval plan architecture.
- Keeps domain-specific ranking logic inside adapters and generic network logic in shared modules.
- Supports both competition-focused retrieval quality and later reuse by the user.

Cons:
- More initial implementation work than direct patching.

### 3. Search-platform rewrite

Adopt a full search-service architecture similar to `web-search-fast`, then rebuild adapters on top of it.

Pros:
- Maximum flexibility and serviceability.

Cons:
- Too much change away from the current high-precision competition architecture.
- Large risk of spending time on infrastructure instead of score-driving retrieval quality.

## Recommended Architecture

Keep the existing runtime shape:

- `/route` still determines `policy`, `academic`, `industry`, or `mixed`
- `/retrieve` still executes first-wave concurrency and fallback chains
- `/answer` still relies on canonical evidence, evidence packs, and citation-gated synthesis

Only the adapter internals change. Each live adapter will follow the same two-stage pattern:

1. `discovery`
   - find candidate result URLs or records
2. `normalize/enrich`
   - fetch page or metadata
   - extract the structured fields needed by the evidence layer
   - emit normalized `RetrievalHit` objects

Shared support modules will live under `skill/retrieval/live/`:

- `clients/`
  - HTTP client wrappers
  - general web-search engine discovery
  - optional headless browser fetch
- `parsers/`
  - SERP parsing
  - official policy page metadata extraction
  - industry page content extraction
  - academic API response normalization
- `cache.py`
  - short-lived search and page cache helpers

Fixture-backed behavior remains available behind an explicit config flag for tests and offline development, but live mode becomes the default runtime path.

## Source Strategy By Domain

### Policy

Policy answers score best when evidence carries observed authority and date/version metadata. The policy adapters therefore stay authority-first.

Primary behavior:

- discover candidate official pages through domain-restricted queries against official sites
- prefer official and regulator domains only
- use general search engines only to discover official links, not as a source of evidence themselves

Fallback behavior:

- broader allowlist search for official mirrors, regulator notices, or interpretive pages on approved domains
- optional headless fetch when plain HTTP cannot retrieve usable content

Acceptance rules:

- non-allowlisted pages do not enter the main policy evidence path
- pages missing both authority and any observed date are rejected
- pages with observed `version`, `publication_date`, or `effective_date` are preferred

### Academic

Academic answers score best when evidence includes strong paper metadata.

Primary behavior:

- query Semantic Scholar for structured scholarly results
- query arXiv for preprints and identifier-backed metadata

Fallback behavior:

- optional general search only to discover DOI landing pages or paper homepages when structured sources are sparse

Acceptance rules:

- prefer DOI-backed and peer-reviewed results over preprints
- preserve `doi`, `arxiv_id`, `first_author`, `year`, and `evidence_level`
- continue merging variants through the existing canonical evidence layer

### Industry

Industry questions need broader open-web recall. This is the domain where the reference repository's multi-engine search approach is most useful.

Primary behavior:

- run `DuckDuckGo`, `Bing`, and `Google` discovery in parallel when enabled
- merge candidates and remove duplicates by canonical URL

Enrichment behavior:

- fetch page content or snippet context
- assign deterministic credibility tiers:
  - `company_official`
  - `industry_association`
  - `trusted_news`
  - `general_web`

Acceptance rules:

- prioritize query alignment first, then credibility tier
- preserve a strong official/association result when available so the answer layer gets higher-quality evidence

### Mixed

Mixed queries continue to use the existing primary and supplemental route model.

- the primary route stays authority-first
- the supplemental route improves coverage
- industry and policy supplemental retrieval may use general discovery, but only the route-appropriate records survive into canonical evidence

## Search, Browser, and Fetch Strategy

General discovery is shared, but it does not replace domain strategy.

- `policy` and `academic` use general search only as a discovery fallback
- `industry` uses multi-engine search as a primary discovery path

Headless browser rules:

- default to headless operation only
- prefer plain HTTP/API retrieval first
- use the browser when:
  - the SERP requires JS or anti-bot evasion beyond simple HTTP
  - a page is dynamically rendered
  - a fetch repeatedly fails in plain HTTP mode

The first implementation targets Playwright-driven headless browsing. Browser usage remains optional and controlled through config so offline tests and API-backed paths stay lightweight.

## Ranking, Fallback, and Caching

The current upper-layer retrieval ordering remains unchanged. Live adapters must emit better `RetrievalHit` inputs, not replace the existing scoring stack.

Per-domain ranking emphasis:

- `policy`: authority and observed date/version metadata
- `academic`: DOI/arXiv identity and evidence level
- `industry`: query match then credibility tier

Fallback chains stay compatible with current retrieval planning:

- `policy_official_registry` -> `policy_official_web_allowlist_fallback`
- `academic_semantic_scholar` and `academic_arxiv` remain parallel first-wave sources
- `industry_ddgs` internally manages multi-engine fallback and dedupe

Caching rules:

- search results: short TTL
- page content: medium TTL
- academic metadata: longer TTL
- caches are bounded and optional so tests can disable them

## Config and Runtime Controls

New config should live under `skill/config/` and environment variables should control:

- live vs fixture adapter mode
- per-source timeout overrides
- search engine enablement
- browser enablement and headless mode
- API keys where needed
- cache TTLs

The default live runtime must still obey bounded request deadlines so `/answer` cannot hang indefinitely on open-web retrieval.

## Testing Strategy

Fixture-backed tests remain the contract baseline.

Add three test layers:

1. unit tests
   - parsers
   - query builders
   - metadata extraction
2. adapter contract tests
   - verify live adapter normalization and ranking from mocked network responses
3. optional live integration tests
   - only run when environment flags and network dependencies are present

The benchmark harness should continue working locally, but benchmark latency expectations must be revised because live retrieval cannot be interpreted like fixture-only runs.

## Success Criteria

- Default runtime path uses live network-backed adapters instead of fixture-only results.
- Hidden queries outside the current fixtures can still retrieve grounded evidence.
- Existing retrieval and answer contracts remain stable.
- Offline unit and contract tests remain deterministic.
- Live mode degrades conservatively when a source is unavailable rather than inventing evidence.
