# Official Source Expansion Design

**Date:** 2026-04-14

**Goal:** Expand the current live retrieval stack with additional public official channels that improve score-oriented retrieval quality without widening the routing surface or destabilizing latency.

## Scope

- Keep the existing `/route` -> `/retrieve` -> `/answer` contracts unchanged.
- Keep the existing adapter registry and source IDs stable unless a new source ID is required for meaningful planner control.
- Add the following worthwhile public official channels:
  - `OpenAlex` as an official scholarly metadata fallback inside the academic metadata path
  - `Europe PMC` as an official biomedical literature fallback inside the preprint/academic path
  - `Federal Register API` as an official US policy fallback inside the policy path
  - `SEC EDGAR search` as an official company-filings supplement inside the industry path
- Expand official policy-domain coverage for Chinese law and regulation sites through the existing allowlist path.

## Recommended Approach

- Strengthen existing adapters before adding planner complexity.
- Keep `policy`, `academic`, and `industry` source IDs mostly stable so evidence ranking and answer fast paths do not need broad changes.
- Treat new channels as upstream official sources inside the current adapters:
  - `academic_semantic_scholar` can fall back to `OpenAlex`
  - `academic_arxiv` can fall back to `Europe PMC`
  - `policy_official_registry` can consult `Federal Register` for US-style regulation queries
  - `industry_ddgs` can merge `SEC` filing hits for filing-oriented company queries

## Why This Approach

- It improves recall with official sources immediately.
- It avoids multiplying first-wave planner sources before the current latency budget is under tighter control.
- It preserves the current evidence contracts, test shape, and answer-layer behavior.

## Non-Goals

- No new route labels.
- No broad retrieval-engine rewrite.
- No login-gated or demo-key-only sources on the main path.
