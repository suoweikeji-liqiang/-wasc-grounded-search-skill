# Roadmap: WASC High-Precision Search Skill

## Overview

This roadmap delivers a competition-first search Skill that reliably answers policy, industry, and academic benchmark queries with source-grounded, structured outputs under strict runtime and cost constraints. Phases follow the natural capability chain from query understanding, to retrieval, to evidence handling, to grounded answer generation, and finally repeatable reliability validation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Query Routing & Core Path Guardrails** - Users get correctly typed queries and source-family routing without browser automation.
- [ ] **Phase 2: Multi-Source Retrieval by Domain** - Users receive resilient concurrent retrieval with domain-aware source prioritization.
- [ ] **Phase 3: Evidence Normalization & Budgeted Context** - Users get deduplicated, normalized, top-K evidence prepared for synthesis.
- [ ] **Phase 4: Grounded Structured Answer Generation** - Users receive structured answers with claim-to-source traceability and explicit outcome states.
- [ ] **Phase 5: Runtime Reliability & Benchmark Repeatability** - Users can run stable benchmark evaluations with enforced latency/token budgets.

## Phase Details

### Phase 1: Query Routing & Core Path Guardrails
**Goal**: Users can submit any benchmark query and have it deterministically routed to the right source families through a non-browser core execution path.
**Depends on**: Nothing (first phase)
**Requirements**: ROUT-01, ROUT-02, ROUT-03
**Success Criteria** (what must be TRUE):
  1. User can submit a query and receive a route label of policy/regulation, industry information, academic literature, or mixed.
  2. User can observe that selected retrieval source families match the detected query type.
  3. User can get end-to-end responses through the main path without Playwright or similar browser automation.
**Plans**: TBD

### Phase 2: Multi-Source Retrieval by Domain
**Goal**: Users can receive robust retrieval results from multiple concurrent sources with deterministic fallback and domain-appropriate priority.
**Depends on**: Phase 1
**Requirements**: RETR-01, RETR-02, RETR-03, RETR-04, RETR-05
**Success Criteria** (what must be TRUE):
  1. User can receive retrieval results assembled from multiple sources running concurrently with bounded per-source timeouts.
  2. User can still get a response when one or more retrieval sources fail, and fallback behavior is consistent across repeated runs.
  3. User can observe policy queries prioritize official/authoritative sources ahead of lower-authority sources.
  4. User can observe academic queries prioritize structured scholarly sources (for example Semantic Scholar/arXiv).
  5. User can receive industry answers that combine multiple sources using credibility-aware ordering.
**Plans**: TBD

### Phase 3: Evidence Normalization & Budgeted Context
**Goal**: Users can get clean, consolidated evidence sets with domain-specific metadata quality and bounded context size.
**Depends on**: Phase 2
**Requirements**: EVID-01, EVID-02, EVID-03, EVID-04
**Success Criteria** (what must be TRUE):
  1. User can receive answers based on evidence that has been deduplicated and reranked before synthesis.
  2. User can see policy evidence annotated with authority plus effective/publication date and jurisdiction/version when available.
  3. User can receive academic evidence where duplicate/preprint/published variants are normalized into canonical citations.
  4. User can receive outputs built from a bounded top-K evidence set that controls token usage.
**Plans**: TBD

### Phase 4: Grounded Structured Answer Generation
**Goal**: Users can receive judge-optimized structured answers where factual claims are source-traceable and answer state is explicit.
**Depends on**: Phase 3
**Requirements**: OUTP-01, OUTP-02, OUTP-03
**Success Criteria** (what must be TRUE):
  1. User can receive output that always includes conclusion, key points, source links, and uncertainty/gap notes.
  2. User can trace each key factual claim to at least one cited source or quoted evidence unit.
  3. User can clearly distinguish whether the result is a grounded success, insufficient evidence case, or retrieval failure case.
**Plans**: TBD

### Phase 5: Runtime Reliability & Benchmark Repeatability
**Goal**: Users can evaluate the system repeatedly under WASC constraints with predictable completion, budget compliance, and measurable performance.
**Depends on**: Phase 4
**Requirements**: RELY-01, RELY-02, RELY-03
**Success Criteria** (what must be TRUE):
  1. User can run benchmark workloads repeatedly with stable completion behavior under contest runtime constraints.
  2. User can execute a repeatable 10-task × 5-run harness and obtain recorded latency, token usage, and success-rate metrics.
  3. User can verify responses consistently respect configured latency and token budgets during runtime.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Query Routing & Core Path Guardrails | 0/TBD | Not started | - |
| 2. Multi-Source Retrieval by Domain | 0/TBD | Not started | - |
| 3. Evidence Normalization & Budgeted Context | 0/TBD | Not started | - |
| 4. Grounded Structured Answer Generation | 0/TBD | Not started | - |
| 5. Runtime Reliability & Benchmark Repeatability | 0/TBD | Not started | - |
