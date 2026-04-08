# Architecture Research

**Domain:** Competition-grade routed search skill (policy / industry / academic)
**Researched:** 2026-04-07
**Confidence:** MEDIUM-HIGH

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            API / Skill Interface Layer                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  Query API  │  Input Validator  │  Request Budget Guard  │  Output Formatter│
└──────┬───────────────┬──────────────────────┬──────────────────────┬─────────┘
       │               │                      │                      │
       ▼               ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Orchestration & Policy Layer                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  Intent Classifier  │  Route Planner  │  Runtime Controller  │  Fallback FSM │
│ (policy/industry/   │ (source plan +  │ (timeouts/retries/   │ (degrade path │
│  academic/mixed)    │  query expansion)│  concurrency limits) │  management)  │
└───────────┬──────────────────────┬──────────────────────┬────────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Retrieval Execution Layer                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Source Adapters (typed, isolated):                                           │
│ - Policy: gov/regulation official domains                                    │
│ - Industry: web/meta search + high-cred domains                              │
│ - Academic: Semantic Scholar + arXiv                                         │
│                                                                              │
│ Retrieval Engine: Async fan-out, per-source timeout, circuit breaker         │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Ranking, Compression, and Evidence Layer                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Canonicalizer → Deduper → BM25/RRF Fusion → Evidence Scorer → Token Pruner  │
│                           (source trust + recency + relevance)               │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Grounded Synthesis & Verification Layer               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Prompt Builder (strict citation contract) → MiniMax-M2.7 → Citation Checker │
│                                  → Structured Result Assembler               │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                             State, Cache, and Observability                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Query Cache │ Source Response Cache │ Metrics (latency/tokens/success) │ Logs │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Query API + Validator | Accept query and enforce schema/limits | FastAPI/Flask handler + pydantic |
| Intent Classifier | Classify policy/industry/academic/mixed | Rule-first classifier (0-token) + optional light LLM fallback |
| Route Planner | Choose sources + expansion strategy by intent | Static routing table + small heuristic scorer |
| Runtime Controller | Enforce latency/token/concurrency budgets | Deadline propagation + semaphore + timeout policy |
| Source Adapters | Isolate each external provider behavior | One adapter per provider, uniform interface |
| Retrieval Engine | Async multi-source retrieval | asyncio/httpx with per-source timeout and cancellation |
| Fusion Ranker | Merge and rank candidates robustly | BM25 + Reciprocal Rank Fusion (RRF) |
| Evidence Scorer | Prefer trust + recency + relevance | Weighted score with domain trust priors |
| Token Pruner | Keep only highest-value evidence slices | Passage-level truncation and dedupe |
| Grounded Synthesizer | Generate structured answer with citations | Single MiniMax-M2.7 call with strict JSON schema |
| Citation Checker | Validate each claim linked to evidence | Claim→source index mapping + missing-citation flags |
| Cache & Metrics | Stability and replay efficiency | SQLite/DiskCache + Prometheus-style metrics |

## Recommended Project Structure

```text
skill/
├── api/                    # External interface
│   ├── entry.py            # main request handler
│   ├── schema.py           # input/output models
│   └── formatter.py        # final structured response
├── orchestrator/           # Routing and runtime governance
│   ├── intent.py           # rule-based classifier
│   ├── planner.py          # source plan + query expansion rules
│   ├── budget.py           # latency/token budget accounting
│   └── fallback_fsm.py     # deterministic degradation state machine
├── retrieval/              # External fetch execution
│   ├── engine.py           # async fan-out/fan-in
│   ├── adapters/
│   │   ├── policy_official.py
│   │   ├── industry_web.py
│   │   ├── semantic_scholar.py
│   │   └── arxiv.py
│   └── normalize.py        # normalize raw hits into common doc format
├── ranking/                # Recall-to-precision pipeline
│   ├── dedupe.py
│   ├── bm25.py
│   ├── rrf.py
│   ├── evidence_score.py
│   └── prune.py
├── synthesis/              # Grounded generation
│   ├── prompt.py
│   ├── generator.py
│   ├── citation_check.py
│   └── uncertainty.py
├── infra/                  # Shared infra
│   ├── cache.py
│   ├── http_client.py
│   ├── metrics.py
│   └── logging.py
└── tests/
    ├── shadow_benchmark.py
    ├── stability_50_runs.py
    └── route_contracts.py
```

### Structure Rationale

- **orchestrator/** is isolated so policy logic changes don’t affect retrievers.
- **retrieval/adapters/** prevents provider-specific failures from contaminating core logic.
- **ranking/** remains deterministic and testable for stability under repeated runs.
- **synthesis/** is thin and grounded, keeping LLM calls minimal and auditable.

## Architectural Patterns

### Pattern 1: Route-then-Retrieve (not Retrieve-everything)

**What:** Determine query intent first, then call only source families that fit.
**When to use:** Strict runtime/token budgets and mixed-domain queries.
**Trade-offs:** Requires robust intent rules; misroute risk mitigated by mixed fallback.

### Pattern 2: Deadline-Driven Orchestration

**What:** Every stage gets a sub-budget from one end-to-end deadline.
**When to use:** Hard scoring on latency and stability.
**Trade-offs:** May reduce completeness on very hard queries, but keeps runs reliable.

### Pattern 3: Deterministic Degradation FSM

**What:** Explicit fallback states when failures occur (source timeout, API error, ranking empty).
**When to use:** Competition environments with repeated-run stability scoring.
**Trade-offs:** Less “smart” than free-form agent behavior, much more predictable.

## Data Flow

### Request Flow (explicit direction)

```text
User Query
  ↓
Input Validator
  ↓
Intent Classifier
  ↓
Route Planner (sources + query variants + budgets)
  ↓
Async Retrieval Engine
  ↓
Canonicalize + Deduplicate
  ↓
BM25/RRF Fusion + Trust/Recency Scoring
  ↓
Token Pruning (top evidence slices only)
  ↓
Grounded Prompt Builder
  ↓
MiniMax-M2.7 (single synthesis call)
  ↓
Citation Checker + Uncertainty Annotator
  ↓
Structured Output:
{ conclusion, key_points[], sources[], time_or_version, uncertainty[] }
```

### Failure/Degradation Flow

```text
Source Timeout/Error
  ↓
Adapter-level retry (bounded)
  ↓
Circuit breaker opens for failing source
  ↓
Fallback FSM:
  A) Switch to backup source family
  B) Reduce query variants
  C) Skip heavy compression
  D) Return partial but structured answer with explicit gaps
```

### Key Data Flows

1. **Policy Query Flow:** Validator → intent=policy → official-source adapters first → strict recency/version scoring → citation-heavy output.
2. **Academic Query Flow:** Validator → intent=academic → Semantic Scholar/arXiv first → metadata-prioritized ranking → paper-centric structured summary.
3. **Mixed Query Flow:** Primary intent route + one secondary route only → merged evidence with provenance tags.

## Component Boundaries (what talks to what)

| Component | Talks To | Must NOT talk to directly |
|-----------|----------|---------------------------|
| API Layer | Orchestrator only | Source adapters, model client |
| Intent/Planner | Retrieval Engine, Budget module | Raw provider SDKs |
| Retrieval Engine | Source adapters only | LLM synthesis modules |
| Rank/Prune Layer | Retrieval output + config | External APIs |
| Synthesis Layer | Rank/Prune output + model client | Raw retrieval adapters |
| Citation Checker | Synthesis output + evidence index | External APIs |
| Cache/Metrics | All layers (shared infra API) | Business logic branching |

## Suggested Build Order (dependency-aware)

1. **Domain model + schemas + structured output contract**
   - Dependency base for all modules.
2. **Source adapters + async retrieval engine**
   - Needed before routing quality can be measured.
3. **Intent classifier + route planner (rule-first)**
   - Enables domain-specific retrieval precision.
4. **Deterministic ranking (dedupe + BM25 + RRF + trust score)**
   - Core precision/cost control.
5. **Budget controller + fallback FSM**
   - Critical for stability/latency scoring.
6. **Grounded synthesis + citation checker**
   - Final accuracy/usability polish under one-call policy.
7. **Caching + observability + shadow benchmark harness**
   - Required for iteration and 50-run stability tuning.

Dependency chain:
`Schemas → Retrieval → Routing → Ranking → Runtime Control → Synthesis → Observability`

## Scaling Considerations (competition-focused)

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k runs/day | Single-process async service + in-memory/SQLite cache |
| 1k-100k runs/day | Split retrieval workers, centralized cache, per-source rate governance |
| 100k+ runs/day | Queue-backed retrieval, source-specific worker pools, adaptive routing by SLA |

### Scaling Priorities

1. **First bottleneck:** External source latency variance → solve with tighter timeouts, hedged requests, caching.
2. **Second bottleneck:** Token explosion from noisy evidence → solve with stricter pruning and one-pass synthesis.

## Anti-Patterns

### Anti-Pattern 1: “One giant agent loop”
**What people do:** Let a general agent browse/search/reason indefinitely.
**Why it's wrong:** Unbounded latency/token use, unstable repeated runs.
**Do this instead:** Deterministic staged pipeline with explicit budgets and stop conditions.

### Anti-Pattern 2: “Uniform source strategy for all query types”
**What people do:** Use one generic search path for policy/industry/academic.
**Why it's wrong:** Low authority for policy, weak recall for academic, noisy industry results.
**Do this instead:** Intent-based source routing with trust priors and route-specific ranking.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Semantic Scholar API | Typed adapter + bounded retry | Use key-aware throttling, monitor status page |
| arXiv API | Typed adapter + strict pacing | Respect 1 request/3s guidance; cache aggressively |
| Web search provider(s) | Pluggable adapter interface | Keep at least one backup provider |
| MiniMax-M2.7 | Single-call synthesizer client | Strict prompt contract + JSON validation |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| API ↔ Orchestrator | Sync function contract | No provider coupling |
| Orchestrator ↔ Retrieval | Plan object + async calls | Deadline propagated |
| Retrieval ↔ Ranking | Canonical document list | Provenance preserved |
| Ranking ↔ Synthesis | Evidence pack (bounded) | Enforce token ceiling |
| Synthesis ↔ Citation Checker | Structured claims + source indices | Must fail-closed on missing citation |

## Confidence Notes

- **HIGH confidence:** arXiv request pacing/ToU limits and SearXNG timeout/pooling guidance (official docs).
- **MEDIUM confidence:** Semantic Scholar operational limits from product/docs pages (official but may change by endpoint/account).
- **MEDIUM confidence:** BM25+RRF and routed retrieval architecture recommendations (industry + research convergence, less single canonical standard).

## Sources

- arXiv API User Manual: https://info.arxiv.org/help/api/user-manual.html
- arXiv API Terms of Use: https://info.arxiv.org/help/api/tou.html
- Semantic Scholar API overview: https://www.semanticscholar.org/product/api
- Semantic Scholar API docs: https://api.semanticscholar.org/api-docs/
- Semantic Scholar API status: https://status.api.semanticscholar.org/
- SearXNG outgoing settings (timeouts/pooling): https://docs.searxng.org/admin/settings/settings_outgoing.html
- Brave Search API rate limiting guide: https://api-dashboard.search.brave.com/documentation/guides/rate-limiting
- NIST Information Quality Standards: https://www.nist.gov/director/nist-information-quality-standards
- EU Code of Practice on Disinformation (policy provenance context): https://digital-strategy.ec.europa.eu/en/policies/code-practice-disinformation
