# Phase 3: Evidence Normalization & Budgeted Context - Research

**Researched:** 2026-04-12
**Domain:** Evidence normalization, canonicalization, and budgeted context packing
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Evidence unit shape
- **D-01:** The canonical evidence unit should be **document + retained evidence slices**, not document-only and not slice-only.
- **D-02:** Phase 3 should keep both the **raw retrieval record** and a **normalized canonical record** internally.
- **D-03:** Each canonical document should retain **at most 2 evidence slices** by default.
- **D-04:** The normalized evidence object should optimize first for **downstream traceability**, not implementation minimalism and not maximum recall at any cost.

### Duplicate collapse policy
- **D-05:** **Policy** duplicates should collapse by **document identity plus version/date-aware canonical matching**, not by URL-only and not by title-similarity alone.
- **D-06:** **Academic** duplicates should use canonical key priority **DOI > arXiv ID > title + first author + year**.
- **D-07:** **Industry** content should use **conservative near-duplicate collapse** based on same-domain plus high title/snippet similarity, not event-level merging.
- **D-08:** When duplicate records contain complementary metadata, the system should **merge the supplemental metadata into the canonical record** rather than discard it.

### Policy metadata completeness
- **D-09:** A policy record missing `version` may still enter the evidence pack if the source is otherwise credible, but it must be explicitly marked `version_missing`.
- **D-10:** `publication_date` and `effective_date` must remain separate fields; if `effective_date` is unknown, the normalized record should say so explicitly rather than collapsing both into one generic date.
- **D-11:** Missing policy `jurisdiction` should not cause automatic rejection when other signals are strong, but the record must be labeled `jurisdiction_inferred` or `jurisdiction_unknown` instead of silently defaulting to national scope.
- **D-12:** The minimum bar for policy evidence entering the pack is **authority + at least one date field**. `jurisdiction` and `version` may be missing only if the normalized record marks that incompleteness explicitly.

### Academic canonicalization
- **D-13:** When a preprint and a formally published paper match, the **published version becomes the canonical record**.
- **D-14:** Non-canonical variants should be preserved as **linked variants** under the canonical academic record, not discarded and not kept as full independent evidence entries.
- **D-15:** Academic evidence should expose an explicit evidence level such as **`peer_reviewed`, `preprint`, `survey_or_review`, or `metadata_only`**.
- **D-16:** Heuristic academic merges are allowed when DOI is unavailable, but they must carry a **`canonical_match_confidence=heuristic`** style marker rather than pretending to be a strong identifier match.

### Budgeted context packing
- **D-17:** Evidence packing should use a **hard token budget plus a top-K ceiling**, not fixed-K alone and not token-only without a record cap.
- **D-18:** Packing should use **one global budget**, but for mixed queries the supplemental route should receive a **small protected minimum share** so it can still contribute supporting evidence while the primary route remains dominant.
- **D-19:** When over budget, the system should **prune low-scoring slices before dropping whole documents**.
- **D-20:** Full budget accounting should remain internally available, while external response surfaces should expose only whether clipping/pruning occurred rather than detailed internal budget telemetry.

### Claude's Discretion
- Exact normalized field names and Python model boundaries, as long as the distinction between raw records, canonical records, linked variants, and retained slices remains explicit.
- Exact duplicate-similarity thresholds for industry near-duplicate collapse and heuristic academic matching.
- Exact token-budget values, slice scoring formula, and clip-indicator field name, as long as hard-budget enforcement and supplemental-route minimum share are preserved.

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVID-01 | User can receive answers whose cited evidence is deduplicated and reranked before synthesis. | Add a raw-to-canonical evidence layer plus deterministic evidence scoring and packing. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [VERIFIED: D:/study/WASC/skill/retrieval/orchestrate.py] |
| EVID-02 | User can receive policy answers that include source authority, effective date or publication date, and version or jurisdiction when available. | Add policy metadata completeness fields and explicit incompleteness flags. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] |
| EVID-03 | User can receive academic answers that normalize duplicate/preprint/published records into a canonical citation set. | Add DOI/arXiv/title-author-year canonical keys plus linked variants. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] |
| EVID-04 | User can receive answers that keep only a bounded top-K evidence set to control token cost. | Add hard budget packing, top-K ceiling, and slice-first pruning. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- `比赛.txt` is authoritative for runtime and contest requirements. [VERIFIED: D:/study/WASC/CLAUDE.md]
- The core path must remain browser-free. [VERIFIED: D:/study/WASC/CLAUDE.md]
- Optimize for contest scoring axes rather than generic product breadth. [VERIFIED: D:/study/WASC/CLAUDE.md]
- Use observed repo tooling rather than inventing a separate build/test stack. [VERIFIED: D:/study/WASC/CLAUDE.md] [VERIFIED: D:/study/WASC/pyproject.toml]

## Summary

Phase 3 needs a new internal evidence layer, not just a new sort function. The current retrieval engine normalizes adapter output into flat `RetrievalHit` objects and does not preserve richer raw payloads, which conflicts with locked decision D-02 unless the retrieval outcome grows additive raw-record support. [VERIFIED: D:/study/WASC/skill/retrieval/engine.py] [VERIFIED: D:/study/WASC/skill/retrieval/models.py] [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]

The other key planning fact is metadata scarcity. Current adapter fixtures expose `title`, `url`, and `snippet`, but not policy version/jurisdiction/date or academic DOI/author/year, so EVID-02 and EVID-03 need richer synthetic fixtures in Wave 0 even if live adapters stay simple for now. [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_registry.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_web_allowlist.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_semantic_scholar.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_arxiv.py]

**Primary recommendation:** Plan Phase 3 as `RetrievalHit` ingress -> `RawEvidenceRecord` capture -> domain-specific canonicalization -> `EvidencePack` budgeter, implemented in a new `skill/evidence/` package and wired into `skill/retrieval/orchestrate.py` after `prioritize_hits()`. [VERIFIED: D:/study/WASC/skill/retrieval/orchestrate.py] [VERIFIED: D:/study/WASC/skill/retrieval/priority.py] [ASSUMED]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | `2.12.5` (PyPI upload `2025-11-26`) [VERIFIED: PyPI JSON API] | Strict evidence/API models | Already used in `skill/api/schema.py`; official docs support the validators Phase 3 needs for response and evidence invariants. [VERIFIED: D:/study/WASC/skill/api/schema.py] [CITED: https://docs.pydantic.dev/latest/concepts/validators/] |
| `dataclasses` | stdlib [CITED: https://docs.python.org/3/library/dataclasses.html] | Frozen internal raw/canonical records | Matches the repo’s existing immutable runtime pattern. [VERIFIED: D:/study/WASC/skill/retrieval/models.py] |
| `rapidfuzz` | `3.14.5` (PyPI upload `2026-04-07`) [VERIFIED: PyPI JSON API] | Conservative near-duplicate similarity | Fits industry same-domain title/snippet matching and heuristic academic fallback without hand-built string logic. [CITED: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html] [CITED: https://rapidfuzz.github.io/RapidFuzz/Usage/process.html] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastapi` | `0.135.3` (PyPI upload `2026-04-01`) [VERIFIED: PyPI JSON API] | Existing `/retrieve` surface | Use only for additive response contract work; keep normalization logic outside the API layer. [VERIFIED: D:/study/WASC/skill/api/entry.py] |
| `pytest` | `9.0.3` on PyPI, `8.4.2` installed locally [VERIFIED: PyPI JSON API] [VERIFIED: local environment] | Phase 3 regressions | Use for canonicalization and packing tests; local env currently needs plugin autoload disabled. [VERIFIED: local environment] |
| `MiniMax Text Generation API` | docs checked `2026-04-12` [CITED: https://platform.minimax.io/docs/api-reference/text-post] | Post-call token usage calibration | The checked docs show `usage.prompt_tokens` and `usage.completion_tokens`, which is enough for calibration later. [CITED: https://platform.minimax.io/docs/api-reference/text-post] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rapidfuzz` | `difflib` or custom string heuristics [ASSUMED] | `rapidfuzz` is more purpose-built for high-threshold duplicate checks. [CITED: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html] [ASSUMED] |
| Evidence logic inside `skill/retrieval/` only | New `skill/evidence/` package | A separate package better matches the repo’s small-focused-module pattern. [VERIFIED: D:/study/WASC/.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md] [ASSUMED] |
| “Exact” preflight tokenizer emulation | Conservative estimator + hard caps + later calibration | I did not verify a dedicated MiniMax preflight token-count endpoint in this session. [CITED: https://platform.minimax.io/docs/api-reference/text-post] [ASSUMED] |

**Installation:**
```bash
pip install rapidfuzz==3.14.5 pytest==9.0.3
```

## Architecture Patterns

### Recommended Project Structure
```text
skill/
├── evidence/                 # new Phase 3 package [ASSUMED]
│   ├── models.py             # RawEvidenceRecord, CanonicalDocument, EvidenceSlice, LinkedVariant, EvidencePack
│   ├── normalize.py          # parse hints from title/url/snippet
│   ├── dedupe.py             # policy/academic/industry canonical matching
│   ├── score.py              # evidence scoring
│   └── pack.py               # hard budget + top-K ceiling + mixed protected share
├── retrieval/
│   ├── engine.py             # add raw-record capture to outcome
│   └── orchestrate.py        # call evidence layer after prioritize_hits
├── api/
│   └── schema.py             # optional evidence response models / stricter invariants
└── tests/
    ├── test_evidence_normalization.py
    ├── test_evidence_packing.py
    └── test_evidence_integration.py
```

### Pattern 1: Two-Layer Evidence Contract
**What:** Keep `RetrievalHit` as ingress compatibility, then wrap it into `RawEvidenceRecord`; canonicalization should output separate `CanonicalDocument` objects with retained slices and linked variants. [VERIFIED: D:/study/WASC/skill/retrieval/models.py] [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [ASSUMED]
**When to use:** Immediately after retrieval outcome assembly. [VERIFIED: D:/study/WASC/skill/retrieval/orchestrate.py] [ASSUMED]

### Pattern 2: Domain-Dispatched Canonicalization
**What:** Use explicit `policy`, `academic`, and `industry` canonicalizers instead of one fuzzy merge function. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]
**When to use:** After raw-record capture and before global evidence scoring. [VERIFIED: D:/study/WASC/.planning/research/ARCHITECTURE.md] [ASSUMED]

### Pattern 3: Budget-First Evidence Packing
**What:** Score canonical docs, keep at most two slices per doc, reserve a small supplemental floor for mixed queries, then enforce both hard budget and hard doc cap. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]
**When to use:** Final Phase 3 step before API shaping or Phase 4 synthesis.

### Anti-Patterns to Avoid
- **Normalizing inside adapters:** Scatters domain rules across providers. [ASSUMED]
- **URL-only policy dedupe:** Explicitly rejected by locked decisions. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]
- **Fixed-K-only packing:** Locked decisions require budget plus cap. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]
- **Treating current fixtures as metadata-complete:** They are not sufficient for EVID-02/EVID-03 proofs. [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_registry.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_semantic_scholar.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Industry near-duplicate similarity | Custom string-similarity helpers | `rapidfuzz` similarity functions [CITED: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html] | High-threshold duplicate checks are their job. [ASSUMED] |
| Cross-field schema invariants | Ad-hoc dict validation | Pydantic validators [CITED: https://docs.pydantic.dev/latest/concepts/validators/] | Current API schema already uses this pattern. [VERIFIED: D:/study/WASC/skill/api/schema.py] |
| Immutable evidence record types | Manual read-only classes | `@dataclass(frozen=True)` [CITED: https://docs.python.org/3/library/dataclasses.html] | Matches current repo style. [VERIFIED: D:/study/WASC/skill/retrieval/models.py] |
| “Exact” MiniMax preflight token counting | Homegrown exact tokenizer claims | Conservative estimator + hard caps + later calibration from returned usage | The checked docs show post-call usage, not a verified dedicated counter endpoint. [CITED: https://platform.minimax.io/docs/api-reference/text-post] [ASSUMED] |

## Common Pitfalls

### Pitfall 1: Losing raw evidence before normalization
**What goes wrong:** Rich adapter payload is flattened into `RetrievalHit`, so canonicalization loses provenance. [VERIFIED: D:/study/WASC/skill/retrieval/engine.py]
**Why it happens:** `_normalize_hits()` and `RetrievalExecutionOutcome.results` only keep the flat shape. [VERIFIED: D:/study/WASC/skill/retrieval/engine.py] [VERIFIED: D:/study/WASC/skill/retrieval/models.py]
**How to avoid:** Add additive raw-record support to retrieval outcomes before Phase 3 logic. [ASSUMED]
**Warning signs:** You have to reconstruct metadata from API response items. [ASSUMED]

### Pitfall 2: Designing slices as if full documents already exist
**What goes wrong:** Plans assume passage chunking, but current retrieval inputs only contain titles and snippets. [VERIFIED: D:/study/WASC/skill/retrieval/models.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_arxiv.py]
**Why it happens:** The phase talks about slices, while current adapters are still fixture-level retrievers. [VERIFIED: D:/study/WASC/.planning/research/ARCHITECTURE.md] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_registry.py]
**How to avoid:** Use snippet-level slices in Phase 3 and keep the second slice slot for future richer extraction. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [ASSUMED]
**Warning signs:** The plan introduces chunkers without any upstream body text source. [ASSUMED]

### Pitfall 3: Overpromising metadata completeness on thin fixtures
**What goes wrong:** The code structure looks correct, but tests cannot prove policy or academic completeness because the fixtures lack those fields. [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_web_allowlist.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_semantic_scholar.py]
**Why it happens:** Phase 2 fixtures were built for routing and priority, not canonical metadata completeness. [VERIFIED: D:/study/WASC/tests/test_domain_priority.py] [ASSUMED]
**How to avoid:** Add synthetic Phase 3 evidence fixtures for policy versions/dates/jurisdictions and academic DOI/arXiv/published-preprint pairs. [ASSUMED]
**Warning signs:** Tests only assert source IDs or order, never canonical IDs, incompleteness flags, or linked variants. [VERIFIED: D:/study/WASC/tests/test_domain_priority.py] [VERIFIED: D:/study/WASC/tests/test_retrieval_integration.py]

### Pitfall 4: Protected supplemental share becoming symmetric packing
**What goes wrong:** Mixed packs give equal room to the supplemental route and dilute the locked primary-route dominance rule. [VERIFIED: D:/study/WASC/.planning/phases/01-query-routing-core-path-guardrails/01-CONTEXT.md] [VERIFIED: D:/study/WASC/.planning/phases/02-multi-source-retrieval-by-domain/02-CONTEXT.md]
**Why it happens:** The protected share is implemented as a quota instead of a floor. [ASSUMED]
**How to avoid:** Reserve only a small floor for supplemental evidence, then let the remaining budget fill from the global score order. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [ASSUMED]
**Warning signs:** Supplemental docs often outnumber primary docs in mixed packs. [ASSUMED]

### Pitfall 5: Misreading the current local test baseline
**What goes wrong:** `pytest -q` crashes during collection in the current local environment because of ambient `pytest_asyncio` plugin autoload. [VERIFIED: local environment]
**Why it happens:** The repo has no pytest config pinning plugin behavior, and local site-packages leak into collection. [VERIFIED: D:/study/WASC/pyproject.toml] [VERIFIED: local environment]
**How to avoid:** Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` until the project env is isolated or configured. [VERIFIED: local environment]
**Warning signs:** Pytest fails before any test runs. [VERIFIED: local environment]

## Code Examples

### Immutable ingress hit contract
```python
# Source: D:/study/WASC/skill/retrieval/models.py
@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    title: str
    url: str
    snippet: str
    credibility_tier: str | None = None
```

### Mixed-route primary dominance already exists upstream
```python
# Source: D:/study/WASC/skill/retrieval/priority.py
if domain == "mixed":
    primary_hits = [hit for hit in hits if _route_for_hit(hit) == primary_route]
    supplemental_hits = [hit for hit in hits if _route_for_hit(hit) == supplemental_route]
```

### Validator pattern for Phase 3 response invariants
```python
# Source pattern: current Pydantic usage + official validators docs
from pydantic import BaseModel, field_validator

class EvidenceResponse(BaseModel):
    clipped: bool
    dropped_documents: int = 0

    @field_validator("dropped_documents", mode="after")
    @classmethod
    def clipped_requires_drop_count(cls, value: int, info):
        if getattr(info, "data", {}).get("clipped") and value < 1:
            raise ValueError("clipped responses must report at least one dropped document")
        return value
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat retrieval list only | Raw retrieval record plus canonical evidence graph [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [ASSUMED] | Phase 3 scope | Preserves traceability while enabling dedupe and variant linking. |
| URL/title-only duplicate thinking | Domain-specific canonical keys with explicit heuristic markers [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] | Phase 3 scope | Reduces silent false merges. |
| Result-count-only truncation | Hard token budget plus top-K ceiling plus slice-first pruning [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] | Phase 3 scope | Controls context size without dropping entire good docs too early. |
| Implicit metadata gaps | Explicit incompleteness markers such as `version_missing` and `jurisdiction_unknown` [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] | Phase 3 scope | Makes uncertainty inspectable instead of guessed. |

**Deprecated/outdated:**
- Treating flat `RetrieveResponse.results` as the only evidence contract is outdated for this phase because it cannot carry raw provenance, linked variants, or budget telemetry by itself. [VERIFIED: D:/study/WASC/skill/api/schema.py] [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A conservative local token estimator plus hard caps is the right Phase 3 path because I did not verify a dedicated MiniMax preflight token counter in this session. | Standard Stack / Don't Hand-Roll | Budget tuning may need a different integration later. |
| A2 | A separate `skill/evidence/` package is the cleanest boundary for this repo. | Summary / Architecture | Tasks would need regrouping if the team prefers expanding `skill/retrieval/`. |
| A3 | `rapidfuzz` is sufficient for initial industry near-duplicate collapse. | Standard Stack / Don't Hand-Roll | Threshold tuning could under-merge or over-merge until calibrated. |

## Open Questions

1. **Should normalized evidence be exposed on `/retrieve` in Phase 3, or kept internal until Phase 4?**
   - What we know: Phase 3 success criteria are user-visible, while current `/retrieve` only exposes flat `results`. [VERIFIED: D:/study/WASC/.planning/ROADMAP.md] [VERIFIED: D:/study/WASC/skill/api/schema.py]
   - What's unclear: Whether preserving the exact current response shape matters more than direct observability now. [ASSUMED]
   - Recommendation: Add an optional `evidence` field and preserve `results` for compatibility. [ASSUMED]

2. **How should the first token budget defaults be chosen without a verified preflight tokenizer?**
   - What we know: The checked MiniMax docs expose response usage fields, and the repo has no current input-token budgeting module. [CITED: https://platform.minimax.io/docs/api-reference/text-post] [VERIFIED: D:/study/WASC/skill/orchestrator/retrieval_plan.py]
   - What's unclear: The exact budget that best fits future Phase 4 prompts. [ASSUMED]
   - Recommendation: Centralize budget constants in Phase 3 and calibrate them against actual MiniMax usage in Phase 4 or 5. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Phase runtime and tests | ✓ | `3.11.9` locally; project target is `>=3.12` [VERIFIED: local environment] [VERIFIED: D:/study/WASC/pyproject.toml] | Use local `3.11.9` for planning/tests, then validate under `3.12`. [ASSUMED] |
| pytest | Validation commands | ✓ | `8.4.2` locally [VERIFIED: local environment] | Pin in venv if needed. [ASSUMED] |
| pytest-asyncio | Ambient local plugin | ✓ but problematic | `0.23.3` locally; crashes collection under plugin autoload [VERIFIED: local environment] | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` passes. [VERIFIED: local environment] |
| pip | Installing deps | ✓ | `25.2` [VERIFIED: local environment] | — |

**Missing dependencies with no fallback:**
- None. [VERIFIED: local environment]

**Missing dependencies with fallback:**
- Local Python is not yet `3.12`, but current tests can run under `3.11.9`; final contest-parity validation should happen under `3.12`. [VERIFIED: D:/study/WASC/pyproject.toml] [VERIFIED: local environment] [ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` [VERIFIED: D:/study/WASC/tests/test_retrieval_integration.py] |
| Config file | none observed [VERIFIED: D:/study/WASC/pyproject.toml] |
| Quick run command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_domain_priority.py tests/test_retrieval_integration.py -q` [VERIFIED: local environment] |
| Full suite command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` [VERIFIED: local environment] |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVID-01 | Deduplicate and rerank into canonical evidence | unit/integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_normalization.py -k dedupe -q` | ❌ Wave 0 |
| EVID-02 | Policy evidence exposes completeness fields and incompleteness markers | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_normalization.py -k policy -q` | ❌ Wave 0 |
| EVID-03 | Academic preprint/published variants normalize into a canonical set | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_normalization.py -k academic -q` | ❌ Wave 0 |
| EVID-04 | Evidence pack enforces hard budget, top-K ceiling, slice pruning, and mixed protected floor | unit/integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_packing.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_normalization.py tests/test_evidence_packing.py -q` [ASSUMED]
- **Per wave merge:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` [VERIFIED: local environment]
- **Phase gate:** Full suite green before `/gsd-verify-work` [VERIFIED: D:/study/WASC/.planning/config.json]

### Wave 0 Gaps
- [ ] `tests/test_evidence_normalization.py` — canonical IDs, linked variants, incompleteness flags, and merge behavior. [VERIFIED: repository scan]
- [ ] `tests/test_evidence_packing.py` — hard budget, top-K ceiling, slice-first pruning, and mixed-route protected share. [VERIFIED: repository scan]
- [ ] `tests/test_evidence_integration.py` — retrieval outcome -> priority ordering -> evidence pack handoff. [ASSUMED]
- [ ] Synthetic Phase 3 evidence fixtures richer than current adapter fixtures. [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_registry.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/academic_semantic_scholar.py]
- [ ] A project-local pytest config or venv note that avoids the observed ambient plugin crash. [VERIFIED: local environment]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not in Phase 3 scope. [VERIFIED: D:/study/WASC/.planning/ROADMAP.md] |
| V3 Session Management | no | Not in Phase 3 scope. [VERIFIED: D:/study/WASC/.planning/ROADMAP.md] |
| V4 Access Control | no | Not in Phase 3 scope. [VERIFIED: D:/study/WASC/.planning/ROADMAP.md] |
| V5 Input Validation | yes | Pydantic models plus explicit normalization rules for URLs, dates, identifiers, and incompleteness flags. [VERIFIED: D:/study/WASC/skill/api/schema.py] [CITED: https://docs.pydantic.dev/latest/concepts/validators/] [ASSUMED] |
| V6 Cryptography | no | No cryptographic feature is introduced in this phase. [VERIFIED: D:/study/WASC/.planning/ROADMAP.md] |

### Known Threat Patterns for evidence normalization

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Retrieved text contains malicious instructions | Elevation of Privilege | Treat snippets and slices as opaque data, never executable instructions. [ASSUMED] |
| Host/title spoofing causes false authority inference | Spoofing | Infer authority from parsed host and route, not title alone. Existing adapters already parse hosts. [VERIFIED: D:/study/WASC/skill/retrieval/adapters/policy_official_web_allowlist.py] [VERIFIED: D:/study/WASC/skill/retrieval/adapters/industry_ddgs.py] [ASSUMED] |
| Over-aggressive heuristic merges collapse distinct records | Tampering | Use strong identifiers first, label heuristic matches, and keep linked variants. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] |
| Oversized snippets blow the context budget | Denial of Service | Enforce per-slice truncation, global budget, and top-K ceiling before synthesis. [VERIFIED: D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md] [ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `D:/study/WASC/.planning/phases/03-evidence-normalization-budgeted-context/03-CONTEXT.md`
- `D:/study/WASC/.planning/REQUIREMENTS.md`
- `D:/study/WASC/.planning/ROADMAP.md`
- `D:/study/WASC/.planning/STATE.md`
- `D:/study/WASC/CLAUDE.md`
- `D:/study/WASC/pyproject.toml`
- `D:/study/WASC/skill/retrieval/models.py`
- `D:/study/WASC/skill/retrieval/engine.py`
- `D:/study/WASC/skill/retrieval/orchestrate.py`
- `D:/study/WASC/skill/retrieval/priority.py`
- `D:/study/WASC/skill/api/schema.py`
- `D:/study/WASC/skill/orchestrator/retrieval_plan.py`
- `D:/study/WASC/tests/test_retrieval_integration.py`
- `D:/study/WASC/tests/test_domain_priority.py`
- `D:/study/WASC/tests/test_retrieval_concurrency.py`
- PyPI JSON API (`https://pypi.org/pypi/<package>/json`)

### Secondary (MEDIUM confidence)
- `D:/study/WASC/.planning/research/ARCHITECTURE.md`
- `D:/study/WASC/.planning/research/PITFALLS.md`
- `D:/study/WASC/.planning/research/SUMMARY.md`
- `https://docs.pydantic.dev/latest/concepts/validators/`
- `https://docs.python.org/3/library/dataclasses.html`
- `https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html`
- `https://rapidfuzz.github.io/RapidFuzz/Usage/process.html`
- `https://platform.minimax.io/docs/api-reference/text-post`

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - package versions are verified, but token-budget tooling is partly assumption-driven.
- Architecture: HIGH - strongly constrained by current retrieval seams and locked Phase 3 decisions.
- Pitfalls: HIGH - directly supported by current fixture/test limits plus locked metadata and budget rules.

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days)
