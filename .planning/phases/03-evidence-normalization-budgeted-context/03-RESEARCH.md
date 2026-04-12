# Phase 3: Evidence Normalization & Budgeted Context - Research

**Researched:** 2026-04-12
**Domain:** Post-retrieval evidence normalization, canonicalization, and budgeted context packing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Evidence unit shape
- **D-01:** The canonical evidence unit should be **document + retained evidence slices**, not document-only and not slice-only.
- **D-02:** Phase 3 should keep both the **raw retrieval record** and a **normalized canonical record** internally.
- **D-03:** Each canonical document should retain **at most 2 evidence slices** by default.
- **D-04:** The normalized evidence object should optimize first for **downstream traceability**.

### Duplicate collapse policy
- **D-05:** **Policy** duplicates collapse by **document identity plus version/date-aware canonical matching**.
- **D-06:** **Academic** duplicates use canonical key priority **DOI > arXiv ID > title + first author + year**.
- **D-07:** **Industry** content uses **conservative near-duplicate collapse** based on same-domain plus high title/snippet similarity.
- **D-08:** Complementary metadata from duplicates should be **merged into the canonical record**.

### Policy metadata completeness
- **D-09:** Missing `version` is allowed only with explicit `version_missing`-style marking.
- **D-10:** `publication_date` and `effective_date` must remain separate fields.
- **D-11:** Missing `jurisdiction` must be explicit (`jurisdiction_inferred` or `jurisdiction_unknown`), never silently defaulted.
- **D-12:** Policy evidence entering the pack must include **authority + at least one date field**.

### Academic canonicalization
- **D-13:** Published version becomes the canonical academic record when matched.
- **D-14:** Other versions remain **linked variants** under the canonical record.
- **D-15:** Academic evidence exposes explicit level markers such as `peer_reviewed`, `preprint`, `survey_or_review`, or `metadata_only`.
- **D-16:** Heuristic academic merges require an explicit confidence marker.

### Budgeted context packing
- **D-17:** Evidence packing uses a **hard token budget plus a top-K ceiling**.
- **D-18:** Mixed queries use a **global budget** with a **small protected minimum share** for the supplemental route.
- **D-19:** Over-budget trimming should **prune low-scoring slices before dropping whole documents**.
- **D-20:** Detailed budget state stays internal; external surfaces expose only whether clipping/pruning occurred.

### the agent's Discretion
- Exact normalized field names, Python dataclass/Pydantic boundaries, and module boundaries.
- Exact duplicate thresholds and heuristic matching thresholds.
- Exact token-budget constants, scoring weights, and clipping indicator field names.

### Deferred Ideas (OUT OF SCOPE)
- Final answer generation and claim writing.
- Reliability harness and repeated-run benchmark execution.
- Heavy multi-provider scholarly expansion beyond the current Semantic Scholar + arXiv baseline.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVID-01 | User can receive answers whose cited evidence is deduplicated and reranked before synthesis. | Canonical document model, duplicate-collapse pipeline, and evidence scoring/packing stage. |
| EVID-02 | User can receive policy answers that include source authority, effective date or publication date, and version or jurisdiction when available. | Policy metadata contract with completeness markers and minimum-entry rules. |
| EVID-03 | User can receive academic answers that normalize duplicate/preprint/published records into a canonical citation set. | Academic canonical key strategy, linked variant model, and confidence-tagged heuristic merging. |
| EVID-04 | User can receive answers that keep only a bounded top-K evidence set to control token cost. | Hard token budget, top-K ceiling, slice-first pruning, and mixed-route budget share rules. |
</phase_requirements>

## Project Constraints (from local repo)

- The codebase is already **Python-first, schema-first, and deterministic**. New evidence logic should follow frozen dataclass / explicit contract patterns rather than free-form dict mutation. [VERIFIED: `skill/retrieval/models.py`] [VERIFIED: `skill/orchestrator/retrieval_plan.py`]
- Retrieval output is currently a **flat list of `RetrievalHit` items** with only `source_id`, `title`, `url`, `snippet`, and optional `credibility_tier`. Phase 3 should extend this boundary rather than redesign upstream retrieval. [VERIFIED: `skill/retrieval/models.py`] [VERIFIED: `skill/retrieval/orchestrate.py`]
- Mixed-query behavior is already **primary-route dominant** with a single strongest supplemental source. Evidence packing must preserve that asymmetry. [VERIFIED: `.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md`] [VERIFIED: `skill/orchestrator/retrieval_plan.py`]
- Browser automation remains out of scope. Phase 3 planning must stay inside the current browser-free retrieval architecture. [VERIFIED: `.planning/PROJECT.md`] [VERIFIED: `.planning/ROADMAP.md`]

## Summary

Phase 3 should be planned as a **normalization and packing layer inserted after Phase 2 retrieval execution/domain-priority ordering and before Phase 4 answer generation**. The cleanest design is to keep raw retrieval hits intact for audit/debug, then derive canonical evidence records that represent document identity, merged metadata, linked variants, retained evidence slices, and budget-aware scoring state. [VERIFIED: `skill/retrieval/orchestrate.py`] [VERIFIED: `skill/retrieval/engine.py`] [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`]

The strongest planning move is to separate this phase into three implementation concerns:
1. **Contracts and normalization models** for canonical evidence.
2. **Domain-specific merge/scoring logic** for policy, academic, and industry evidence.
3. **Budgeted evidence packing** that turns normalized records into a bounded synthesis-ready evidence set.

This keeps the phase aligned with the current codebase structure and gives Phase 4 a clean handoff boundary for claim-to-source traceability. [VERIFIED: `.planning/research/ARCHITECTURE.md`] [VERIFIED: `.planning/research/PITFALLS.md`]

**Primary recommendation:** Implement Phase 3 around a dedicated evidence module family (`normalize`, `dedupe`, `score`, `pack`) with explicit canonical dataclasses, domain-specific normalizers, and deterministic pruning rules that preserve retained-slice provenance. [VERIFIED: `.planning/research/ARCHITECTURE.md`] [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`]

## Standard Stack

### Core
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| Python dataclasses | Canonical evidence contracts | Existing retrieval plan/result objects already use frozen dataclasses and explicit fields. [VERIFIED: `skill/retrieval/models.py`] [VERIFIED: `skill/orchestrator/retrieval_plan.py`] |
| Pydantic v2 models | API-facing evidence/result surfaces when normalization becomes externally exposed | Existing API contract already uses strict `extra=\"forbid\"` models and field validators. [VERIFIED: `skill/api/schema.py`] |
| `re` / stdlib string normalization | Conservative duplicate heuristics and canonical-key normalization | Keeps Phase 3 deterministic and lightweight before any heavier ranking experimentation. [ASSUMED] |

### Supporting
| Tooling | Purpose | When to Use |
|---------|---------|-------------|
| Existing `skill/retrieval/priority.py` | Domain-first ordering input into evidence scoring | Use as upstream ordering prior, then add normalization-specific scoring on top. [VERIFIED: `skill/retrieval/priority.py`] |
| Existing tests + pytest | Contract and regression verification | Extend current pytest pattern with normalization/canonicalization/packing regressions. [VERIFIED: `tests/test_retrieval_integration.py`] [VERIFIED: `tests/test_domain_priority.py`] [VERIFIED: `tests/test_retrieval_concurrency.py`] |

### Local test-run note
- In this environment, plain `pytest -q` fails during collection because ambient `pytest_asyncio` auto-loads an incompatible plugin hook. Verified working pattern is `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest ...`. [VERIFIED: local command run on 2026-04-12]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deterministic local duplicate heuristics | Fuzzy-matching or embedding-based dedupe | Better semantic clustering, but adds instability/cost too early for this contest-first phase. |
| Separate per-domain pipelines with little shared structure | One shared canonical evidence core with domain plug-ins | Shared core reduces schema drift and makes Phase 4 integration simpler. |
| Pure fixed-K pruning | Token-estimated packing plus K cap | Fixed-K alone is simpler but does not satisfy the explicit bounded-context requirement as robustly. |

## Architecture Patterns

### Recommended Project Structure
```text
skill/
├── evidence/
│   ├── models.py              # canonical evidence dataclasses
│   ├── normalize.py           # raw hit -> canonical candidate records
│   ├── dedupe.py              # domain-specific duplicate collapse
│   ├── score.py               # evidence-level scoring and ranking
│   ├── pack.py                # token budget + top-K pruning
│   └── policy.py              # policy metadata extraction helpers
├── retrieval/
│   ├── orchestrate.py         # insert normalization + packing after priority
│   └── models.py              # keep raw RetrievalHit contract as upstream boundary
└── tests/
    ├── test_evidence_models.py
    ├── test_evidence_policy.py
    ├── test_evidence_academic.py
    ├── test_evidence_dedupe.py
    └── test_evidence_pack.py
```

### Pattern 1: Raw-to-Canonical Two-Layer Evidence Model
**What:** Preserve upstream retrieval hits as immutable raw records, then derive canonical evidence records with normalized identity and merged metadata.
**When to use:** Immediately after Phase 2 prioritized retrieval results are available.
**Why:** This satisfies D-02 and avoids losing provenance needed for later citation tracing. [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`]

### Pattern 2: Domain Plug-ins on a Shared Canonical Core
**What:** Use one shared canonical evidence schema, but plug in domain-specific identity extraction and metadata enrichment rules.
**When to use:** During dedupe and canonicalization.
**Why:** Policy, academic, and industry duplicates behave differently, but Phase 4 still needs one stable evidence contract. [VERIFIED: `.planning/research/PITFALLS.md`] [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`]

### Pattern 3: Slice-First Budget Pruning
**What:** Score retained slices inside each canonical document, prune low-value slices first, and only drop entire documents when necessary.
**When to use:** During budgeted evidence pack creation.
**Why:** This is the direct consequence of D-03 and D-19 and preserves cross-document coverage longer than document-first dropping.

### Pattern 4: Mixed-Route Budget Reserve
**What:** Let primary-route evidence dominate globally, but reserve a small minimum share for supplemental-route evidence in mixed queries.
**When to use:** In the final packing step only, not earlier in duplicate handling.
**Why:** This preserves the Phase 1/2 primary-route contract while preventing supplemental evidence starvation. [VERIFIED: `.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md`] [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`]

### Anti-Patterns to Avoid
- **Collapsing raw and canonical objects into one mutable structure:** makes debugging and later traceability much harder.
- **Using one duplicate rule for all domains:** directly conflicts with locked Phase 3 decisions.
- **Silently inferring missing policy metadata:** violates explicit incompleteness signaling.
- **Dropping preprint/published links after canonicalization:** harms auditability and academic traceability.
- **Budgeting only by count and ignoring content length:** weakens EVID-04 and makes token behavior unstable.

## Recommended Data Contract

### Canonical Evidence Record
The planning target should be a canonical dataclass roughly shaped like:

```python
@dataclass(frozen=True)
class EvidenceSlice:
    text: str
    source_span: str | None
    score: float
    token_estimate: int

@dataclass(frozen=True)
class LinkedVariant:
    source_id: str
    title: str
    url: str
    variant_type: str
    canonical_match_confidence: str

@dataclass(frozen=True)
class CanonicalEvidence:
    evidence_id: str
    domain: str
    canonical_title: str
    canonical_url: str
    raw_hits: tuple[RetrievalHit, ...]
    linked_variants: tuple[LinkedVariant, ...]
    retained_slices: tuple[EvidenceSlice, ...]
    authority: str | None = None
    jurisdiction: str | None = None
    jurisdiction_status: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    version: str | None = None
    version_status: str | None = None
    evidence_level: str | None = None
    canonical_match_confidence: str | None = None
    route_role: str = "primary"
    total_score: float = 0.0
    token_estimate: int = 0
```

The exact field names are flexible, but the plan should preserve these semantics. This gives Phase 4 one evidence object that is rich enough for claim binding without requiring it to understand raw retrieval adapter quirks.

## Common Pitfalls

### Pitfall 1: Canonical identity too weak for policy records
**What goes wrong:** Same regulation appears multiple times because dedupe only uses URL or title similarity.
**Why it happens:** Official sources often expose alternate URLs or repository views.
**How to avoid:** Build policy identity from authority + normalized title + version/date hints, with URL as only one signal.
**Warning signs:** Multiple policy records with the same authority/title but different mirror URLs survive packing.

### Pitfall 2: Academic variants merged without confidence labeling
**What goes wrong:** Preprint and published versions are merged heuristically, but downstream code cannot tell whether the match was strong or weak.
**Why it happens:** DOI is unavailable, so teams silently fall back to approximate title matching.
**How to avoid:** Preserve `canonical_match_confidence` and linked variants explicitly on every heuristic merge.
**Warning signs:** Tests cannot tell exact-ID merges from approximate merges.

### Pitfall 3: Context budget pruning destroys document coverage
**What goes wrong:** Entire lower-ranked documents are removed too early, leaving only one source family represented.
**Why it happens:** Budget logic works at document level only.
**How to avoid:** Score and prune slices first, then documents, while honoring the mixed supplemental minimum share.
**Warning signs:** Mixed query evidence packs routinely contain zero supplemental-route evidence.

### Pitfall 4: Policy incompleteness hidden behind best-effort inference
**What goes wrong:** `jurisdiction` or `version` appears populated even though it was guessed from host/domain.
**Why it happens:** Normalization mixes inferred and observed metadata without explicit status fields.
**How to avoid:** Separate value fields from status fields (`known`, `inferred`, `missing`).
**Warning signs:** No code path can distinguish explicit metadata from inferred metadata.

## Code Examples

Verified patterns from current codebase:

### Frozen contract pattern
```python
# Source: skill/retrieval/models.py
@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    title: str
    url: str
    snippet: str
    credibility_tier: str | None = None
```

### Phase 2 orchestration insertion point
```python
# Source: skill/retrieval/orchestrate.py
outcome = await run_retrieval(...)
prioritized_hits = prioritize_hits(...)
return _shape_response(...)
```

This is the cleanest place to insert `normalize -> dedupe -> score -> pack` before the final API shaping boundary evolves.

### Existing ordered de-duplication style
```python
# Source: skill/retrieval/engine.py
deduped_gaps = tuple(dict.fromkeys(unresolved_gaps))
```

The codebase already prefers deterministic first-seen ordering over probabilistic structures; Phase 3 should keep that style for duplicate collapse.

## State of the Art

| Old Approach | Recommended Phase 3 Approach | Impact |
|--------------|------------------------------|--------|
| Flat retrieval hit list only | Raw hits + canonical evidence record | Preserves provenance while enabling clean normalization. |
| Domain-priority only | Domain-priority + domain-specific canonicalization | Adds evidence quality without disturbing retrieval routing behavior. |
| Count-based result handling | Token-estimated evidence packing with K ceiling | Better budget stability for synthesis. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Token estimates can be approximated cheaply enough with deterministic heuristics in Phase 3, without introducing a tokenizer dependency yet. | Budgeted context packing | If wrong, pruning behavior may drift from real synthesis cost. |
| A2 | Existing retrieval snippets are enough to start slice-level evidence retention without adding a full document-cleaning stage in this phase. | Evidence unit shape | If wrong, retained slices may be too noisy and require an earlier text-cleaning step. |
| A3 | Pydantic exposure of canonical evidence can wait until the internal evidence pipeline stabilizes. | Contracts | If wrong, API churn may happen in Phase 4. |

## Open Questions (RESOLVED)

1. **Should normalization live inside retrieval or in a new module family?**
   - **Resolution:** Use a new `skill/evidence/` module family, with `skill/retrieval/orchestrate.py` as the integration point.
   - **Why this resolves the question:** It keeps Phase 2 retrieval contracts intact while isolating new evidence logic.

2. **What should be the smallest testable unit for packing?**
   - **Resolution:** Make the packing function accept canonical evidence records plus a budget config and return a deterministic evidence pack plus clipping metadata.
   - **Why this resolves the question:** It allows direct unit tests for EVID-04 without spinning the whole retrieval stack.

3. **How should policy metadata absence be represented?**
   - **Resolution:** Use explicit status markers for missing or inferred metadata instead of silent null-only handling.
   - **Why this resolves the question:** It keeps later answer generation honest and testable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python | Evidence pipeline runtime | Yes | Local venv present | Native execution |
| pytest | Contract/regression tests | Yes | Repository already uses pytest | Reuse existing test setup |
| fastapi / pydantic | Existing API layer | Yes | Already in repo environment | Keep internal contracts compatible |

**Missing dependencies with no fallback:**
- None required for planning Phase 3.

**Environment caveat:**
- Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for local pytest commands until plugin isolation is addressed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none currently required |
| Quick run command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py tests/test_evidence_pack.py -q` |
| Full suite command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` |
| Estimated runtime | ~10-20 seconds once Phase 3 tests exist |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVID-01 | Duplicate collapse and reranked synthesis-ready evidence output | unit + integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_dedupe.py tests/test_evidence_pack.py -q` | No - Wave 0 |
| EVID-02 | Policy evidence includes authority/date plus explicit version/jurisdiction handling | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_policy.py -q` | No - Wave 0 |
| EVID-03 | Academic preprint/published variants normalize into canonical citation sets | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_academic.py -q` | No - Wave 0 |
| EVID-04 | Hard token budget + top-K cap with deterministic clipping | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_pack.py -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** Run the smallest relevant Phase 3 test file(s) plus any touched existing regression file.
- **Per plan wave:** Run `pytest -q`.
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_evidence_models.py` - canonical evidence contract and raw/canonical separation
- [ ] `tests/test_evidence_policy.py` - policy metadata completeness and explicit missing/inferred markers
- [ ] `tests/test_evidence_academic.py` - DOI/arXiv/heuristic canonicalization and linked variants
- [ ] `tests/test_evidence_dedupe.py` - industry near-duplicate collapse and metadata merge behavior
- [ ] `tests/test_evidence_pack.py` - hard budget + top-K + mixed-route supplemental reserve

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Yes | Canonical evidence contracts should reject malformed or incomplete internal state transitions where required. |
| V8 Data Protection | Yes | Retrieved text must remain treated as untrusted data; no execution or instruction following from evidence text. |
| V10 Malicious Code | Indirectly | Evidence text and metadata must not be interpreted as commands, templates, or code paths. |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection embedded in retrieved text | Elevation of Privilege | Store retrieved text as inert evidence only; never execute or trust embedded instructions. |
| Poisoned duplicate merge | Tampering | Use conservative match rules and explicit confidence markers for heuristic merges. |
| Metadata spoofing by unofficial pages | Spoofing | Policy metadata requires explicit authority and status markers before entering the pack. |
| Token-budget bypass via oversized slices | Denial of Service | Enforce per-slice token estimate and whole-pack hard budget before synthesis handoff. |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md`
- `.planning/phases/01-query-routing-core-path-guardrails/01-CONTEXT.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`
- `.planning/research/SUMMARY.md`
- `skill/retrieval/models.py`
- `skill/retrieval/engine.py`
- `skill/retrieval/orchestrate.py`
- `skill/retrieval/priority.py`
- `skill/api/schema.py`
- `skill/orchestrator/retrieval_plan.py`
- `tests/test_retrieval_integration.py`
- `tests/test_domain_priority.py`
- `tests/test_retrieval_concurrency.py`

### Secondary (MEDIUM confidence)
- `.planning/phases/02-multi-source-retrieval-by-domain/02-RESEARCH.md` - prior research structure and validation pattern for plan readiness.

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Contracts and integration points: HIGH - directly verified from current codebase.
- Domain canonicalization strategy: HIGH - directly constrained by Phase 3 locked decisions.
- Budget-packing approach: MEDIUM-HIGH - strong alignment with project research and requirements, but exact token heuristics remain an implementation choice.

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days)
