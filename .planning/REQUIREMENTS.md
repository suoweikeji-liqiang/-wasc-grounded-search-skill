# Requirements: WASC High-Precision Search Skill

**Defined:** 2026-04-08
**Core Value:** For any benchmark query, the Skill returns a trustworthy, structured answer with clear source links and minimal unsupported claims.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Routing

- [x] **ROUT-01**: User can submit a query and have it classified into policy/regulation, industry information, academic literature, or mixed.
- [x] **ROUT-02**: User can get results retrieved from source families that match the detected query type.
- [x] **ROUT-03**: User can receive answers without browser automation in the main execution path.

### Retrieval

- [x] **RETR-01**: User can get answers built from multiple retrieval sources executed concurrently with bounded per-source timeouts.
- [x] **RETR-02**: User can receive a response even when one or more retrieval sources fail, through deterministic fallback behavior.
- [x] **RETR-03**: User can get policy answers prioritized toward authoritative original or official sources.
- [x] **RETR-04**: User can get academic answers prioritized toward structured scholarly sources such as Semantic Scholar or arXiv.
- [x] **RETR-05**: User can get industry answers synthesized from multiple sources with credibility-aware ranking.

### Evidence

- [ ] **EVID-01**: User can receive answers whose cited evidence is deduplicated and reranked before synthesis.
- [ ] **EVID-02**: User can receive policy answers that include source authority, effective date or publication date, and version or jurisdiction when available.
- [ ] **EVID-03**: User can receive academic answers that normalize duplicate/preprint/published records into a canonical citation set.
- [ ] **EVID-04**: User can receive answers that keep only a bounded top-K evidence set to control token cost.

### Output

- [ ] **OUTP-01**: User can receive a structured result containing a conclusion, key points, source links, and uncertainty or gaps.
- [ ] **OUTP-02**: User can trace each key factual claim back to at least one cited source or quoted evidence unit.
- [ ] **OUTP-03**: User can distinguish between retrieval failure, insufficient evidence, and successful grounded answers.

### Reliability

- [ ] **RELY-01**: User can run the benchmark workload repeatedly with stable completion behavior under the contest runtime constraints.
- [ ] **RELY-02**: User can evaluate the system with a repeatable 10-task x 5-run benchmark harness that records latency, token usage, and success rate.
- [ ] **RELY-03**: User can get responses that respect explicit latency and token budgets enforced by the runtime pipeline.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Retrieval Quality

- **RQLT-01**: User can benefit from controlled query expansion with 3-5 alternate query views.
- **RQLT-02**: User can see conflicts between sources explicitly called out in the result.
- **RQLT-03**: User can see confidence tiers attached to major claims.

### Optimization

- **OPTI-01**: User can get faster repeated answers through normalized query/result caching.
- **OPTI-02**: User can benefit from more advanced compression or pruning strategies beyond BM25/RRF baseline.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Playwright/Selenium in the main path | Explicitly excluded by user and harmful to speed/stability goals |
| Chat-first multi-step agent behavior | Not aligned with competition-first scoring objective |
| Broad productization beyond benchmarked search skill | Would dilute focus from competition performance |
| Heavy multi-model orchestration | Adds latency, token cost, and instability |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROUT-01 | Phase 1 | Complete |
| ROUT-02 | Phase 1 | Complete |
| ROUT-03 | Phase 1 | Complete |
| RETR-01 | Phase 2 | Complete |
| RETR-02 | Phase 2 | Complete |
| RETR-03 | Phase 2 | Complete |
| RETR-04 | Phase 2 | Complete |
| RETR-05 | Phase 2 | Complete |
| EVID-01 | Phase 3 | Pending |
| EVID-02 | Phase 3 | Pending |
| EVID-03 | Phase 3 | Pending |
| EVID-04 | Phase 3 | Pending |
| OUTP-01 | Phase 4 | Pending |
| OUTP-02 | Phase 4 | Pending |
| OUTP-03 | Phase 4 | Pending |
| RELY-01 | Phase 5 | Pending |
| RELY-02 | Phase 5 | Pending |
| RELY-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-12 after Phase 2 completion*
