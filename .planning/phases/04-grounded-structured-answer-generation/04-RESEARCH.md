# Phase 4: Grounded Structured Answer Generation - Research

**Researched:** 2026-04-12
**Domain:** Grounded answer synthesis, claim-to-evidence binding, and explicit answer-state handling
**Confidence:** HIGH

<carry_forward_constraints>
## Carry-Forward Constraints (no phase CONTEXT.md)

- No dedicated `04-CONTEXT.md` exists for this phase. Planning must therefore inherit project and prior-phase decisions instead of introducing new product preferences. [VERIFIED: `.planning/STATE.md`] [VERIFIED: `.planning/ROADMAP.md`]
- Browser automation remains out of scope; the answer path must stay on top of the existing browser-free retrieval core. [VERIFIED: `.planning/PROJECT.md`] [VERIFIED: `.planning/REQUIREMENTS.md`]
- Phase 3 already made `EvidencePack.canonical_evidence` the retrieval response boundary, so Phase 4 should consume that boundary directly rather than rebuild evidence from raw hits. [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-VERIFICATION.md`] [VERIFIED: `skill/retrieval/orchestrate.py`]
- The competition direction still favors a single bounded synthesis step plus deterministic validation over multi-turn agent loops. [VERIFIED: `.planning/PROJECT.md`] [VERIFIED: `.planning/research/ARCHITECTURE.md`]
- The final output must be judge-friendly: conclusion, key points, source links, and explicit uncertainty or gap notes. [VERIFIED: `.planning/ROADMAP.md`] [VERIFIED: `claude/需求.md`]

</carry_forward_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUTP-01 | User can receive a structured result containing a conclusion, key points, source links, and uncertainty or gaps. | Contract-first answer models, deterministic source shaping, and explicit uncertainty-note assembly. |
| OUTP-02 | User can trace each key factual claim back to at least one cited source or quoted evidence unit. | Evidence-bound citation schema plus fail-closed citation checker against retained slices. |
| OUTP-03 | User can distinguish between retrieval failure, insufficient evidence, and successful grounded answers. | Separate answer-state taxonomy and deterministic state mapping from retrieval outcome plus citation validity. |

</phase_requirements>

## Project Constraints (from local repo)

- There is currently no `skill/synthesis/` package, no answer endpoint, and no model client wrapper in the repository. Phase 4 is the first answer-generation layer. [VERIFIED: `skill/api/entry.py`] [VERIFIED: repo scan of `skill/`]
- Retrieval already returns bounded `canonical_evidence`, `evidence_clipped`, and `evidence_pruned`, which gives Phase 4 enough material to produce quote-level citations without touching adapters. [VERIFIED: `skill/api/schema.py`] [VERIFIED: `skill/retrieval/orchestrate.py`]
- Existing retrieval status taxonomy is `success | partial | failure_gaps`. Phase 4 needs a separate answer-status taxonomy because a partially successful retrieval can still yield a grounded answer if every surfaced key point is cited, while a successful retrieval can still produce insufficient evidence if citations fail validation. [VERIFIED: `skill/retrieval/models.py`] [ASSUMED: grounded-success rule]
- The codebase uses explicit dataclasses and strict Pydantic models, not free-form dict mutation. New synthesis work should follow the same contract-first pattern. [VERIFIED: `skill/evidence/models.py`] [VERIFIED: `skill/api/schema.py`]
- Local pytest collection still requires `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-RESEARCH.md`]

## Summary

Phase 4 should be planned as a new synthesis layer inserted after `execute_retrieval_pipeline(...)` and before the final user-facing answer response. The cleanest execution split is:
1. Lock answer contracts and explicit answer-state taxonomy.
2. Implement prompt building, single-call structured generation, claim-to-evidence validation, and uncertainty derivation.
3. Wire those pieces into a browser-free `/answer` API path and end-to-end tests.

Primary recommendation: use a fail-closed synthesis pipeline that only emits `grounded_success` when every returned key point cites at least one existing `evidence_id` plus `source_record_id` from Phase 3 retained slices. All other non-retrieval-failure cases should degrade to `insufficient_evidence`, with deterministic uncertainty notes explaining clipping, gaps, heuristic academic matches, or missing policy metadata. [VERIFIED: `.planning/ROADMAP.md`] [VERIFIED: `.planning/research/PITFALLS.md`] [VERIFIED: `skill/api/schema.py`]

## Standard Stack

### Core
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| Pydantic v2 | Answer request/response contracts | Already used for API boundary enforcement and `extra="forbid"` models. [VERIFIED: `skill/api/schema.py`] |
| Python dataclasses | Internal synthesis models for key points, citations, and answer state | Matches the repo's current deterministic contract style. [VERIFIED: `skill/evidence/models.py`] |
| Existing canonical evidence models | Grounding boundary for answer generation | Phase 3 already exposes `canonical_evidence` with retained slices and linked variants. [VERIFIED: `skill/evidence/models.py`] |
| Injectable model-client protocol | MiniMax-compatible generation without hard-coding network behavior into tests | No client wrapper exists yet, so an interface boundary keeps tests local and deterministic. [VERIFIED: repo scan] |

### Supporting
| Tooling | Purpose | When to Use |
|---------|---------|-------------|
| `skill/retrieval/orchestrate.py` | Retrieve and bound evidence before synthesis | Reuse as-is for the browser-free answer path. [VERIFIED: `skill/retrieval/orchestrate.py`] |
| `skill/api/schema.py` | External contract surface | Extend with `AnswerRequest` and `AnswerResponse`. [VERIFIED: `skill/api/schema.py`] |
| pytest | Contract, citation-check, orchestration, and endpoint tests | Extend the existing test style with fake model clients and real evidence packs. [VERIFIED: `tests/test_retrieval_integration.py`] |

### Local test-run note
- In this environment, use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest ...` for Phase 4 tests, matching Phase 3's verified workaround. [VERIFIED: `.planning/phases/03-evidence-normalization-budgeted-context/03-RESEARCH.md`]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single-call structured synthesis + post-checker | Free-form answer text with no citation checker | Simpler, but directly risks uncited or dangling claims. |
| Fail-closed citation binding | Link-only citations | Easier to render, but does not satisfy OUTP-02 traceability. |
| One bounded synthesis call | Multi-call self-repair loop | Potentially higher quality, but worse latency/token predictability and more moving parts before Phase 5 reliability work. |
| Separate `/answer` endpoint | Overloading `/retrieve` to sometimes synthesize | Smaller surface area, but mixes evidence retrieval contracts with final answer contracts and makes outcome-state handling harder to reason about. |

## Architecture Patterns

### Recommended Project Structure
```text
skill/
├─ synthesis/
│  ├─ models.py            # answer, key point, citation, source, and state contracts
│  ├─ state.py             # retrieval-state to answer-state mapping
│  ├─ prompt.py            # canonical evidence -> strict synthesis prompt
│  ├─ generator.py         # MiniMax client adapter + strict JSON parsing
│  ├─ citation_check.py    # claim-to-evidence validation
│  ├─ uncertainty.py       # deterministic uncertainty/gap note builder
│  └─ orchestrate.py       # retrieve -> synthesize -> validate -> shape response
├─ api/
│  ├─ schema.py            # AnswerRequest / AnswerResponse models
│  └─ entry.py             # /answer endpoint
└─ tests/
   ├─ fixtures/answer_phase4_cases.json
   ├─ test_answer_contracts.py
   ├─ test_answer_state_mapping.py
   ├─ test_answer_generator.py
   ├─ test_answer_citation_check.py
   ├─ test_answer_integration.py
   └─ test_api_answer_endpoint.py
```

### Pattern 1: Answer-State Taxonomy Separate from Retrieval Status
**What:** Represent final answer state as `grounded_success`, `insufficient_evidence`, or `retrieval_failure`, instead of reusing retrieval-layer `success`, `partial`, and `failure_gaps`.
**When to use:** At the final synthesis boundary.
**Why:** Retrieval success does not guarantee grounded claims, and retrieval partial does not automatically prevent a grounded answer if surfaced claims remain fully cited.

### Pattern 2: Claim-First Citation Binding
**What:** Every key point carries one or more citations pointing to explicit `evidence_id` plus `source_record_id`, optionally with `quote_text`.
**When to use:** In the model output contract and the citation checker.
**Why:** This satisfies OUTP-02 and avoids the common "has links but no supporting span" failure mode. [VERIFIED: `.planning/research/PITFALLS.md`]

### Pattern 3: Fail-Closed Citation Checker
**What:** Post-validate the generated answer against the actual evidence pack; any missing or dangling claim citation prevents `grounded_success`.
**When to use:** Immediately after JSON parsing and before final response shaping.
**Why:** The repo currently has no answer layer, so the most important new safety boundary is between model output and user-visible claims. [ASSUMED]

### Pattern 4: Deterministic Uncertainty Derivation
**What:** Build uncertainty notes from evidence facts such as retrieval gaps, clipping, heuristic academic matches, or missing policy version/jurisdiction markers.
**When to use:** After citation validation and before final response shaping.
**Why:** This keeps honesty grounded in observable system state instead of free-form model hedging. [VERIFIED: `.planning/ROADMAP.md`] [VERIFIED: `.planning/research/FEATURES.md`]

### Pattern 5: Single-Call Synthesis on Bounded Evidence
**What:** Use one structured generation pass over the bounded Phase 3 evidence pack, then validate and downgrade if necessary.
**When to use:** Default Phase 4 path.
**Why:** It matches the contest-first constraints on runtime, token cost, and repeatability while still enabling structured answers. [VERIFIED: `.planning/PROJECT.md`] [VERIFIED: `.planning/research/ARCHITECTURE.md`]

### Anti-Patterns to Avoid
- Rebuilding evidence from raw retrieval hits instead of consuming `canonical_evidence`.
- Returning bare source links with no quote- or slice-level support.
- Letting model output decide answer state without deterministic validation.
- Treating retrieval `partial` as an automatic failure even when all surfaced claims are grounded.
- Exposing internal budget counters or scoring details in the public answer contract.

## Recommended Data Contract

### Structured Answer Model
The planning target should be a synthesis contract roughly shaped like:

```python
AnswerStatus = Literal[
    "grounded_success",
    "insufficient_evidence",
    "retrieval_failure",
]

@dataclass(frozen=True)
class ClaimCitation:
    evidence_id: str
    source_record_id: str
    source_url: str
    quote_text: str

@dataclass(frozen=True)
class KeyPoint:
    key_point_id: str
    statement: str
    citations: tuple[ClaimCitation, ...]

@dataclass(frozen=True)
class SourceReference:
    evidence_id: str
    title: str
    url: str

@dataclass(frozen=True)
class StructuredAnswer:
    answer_status: AnswerStatus
    conclusion: str
    key_points: tuple[KeyPoint, ...]
    sources: tuple[SourceReference, ...]
    uncertainty_notes: tuple[str, ...]
    gaps: tuple[str, ...]
```

Exact field names can vary, but the plan should preserve these semantics:
- one explicit answer status
- one conclusion
- multiple key points with evidence-bound citations
- deduplicated source references
- explicit uncertainty and gaps section

## Common Pitfalls

### Pitfall 1: Link-level citations that are not traceable to retained evidence
**What goes wrong:** Answers include URLs, but reviewers cannot find the supporting statement in the actual evidence slice.
**Why it happens:** Citation models store only links or titles.
**How to avoid:** Require `evidence_id` plus `source_record_id`, and validate quoted text against retained slices.
**Warning signs:** `sources` exist, but key-point citations cannot map back to `retained_slices`.

### Pitfall 2: Retrieval success mislabeled as grounded answer
**What goes wrong:** The retrieval step succeeds, but the synthesized answer still contains uncited or weakly supported claims.
**Why it happens:** The system reuses retrieval status as answer status.
**How to avoid:** Derive answer state after citation validation, not before.
**Warning signs:** `answer_status="grounded_success"` appears even when a key point has zero citations.

### Pitfall 3: Uncertainty notes not grounded in observable evidence conditions
**What goes wrong:** The model adds vague caveats that are not tied to actual clipping, gaps, or metadata ambiguity.
**Why it happens:** Uncertainty is left entirely to the generator.
**How to avoid:** Build uncertainty notes deterministically from retrieval and evidence state.
**Warning signs:** Uncertainty text changes arbitrarily across identical fixtures.

### Pitfall 4: Public contract leaks internal budget telemetry
**What goes wrong:** The final answer payload exposes raw token counts or scorer internals.
**Why it happens:** Teams reuse internal evidence-pack objects directly.
**How to avoid:** Surface only answer status, source references, key-point citations, and high-level uncertainty/gap notes.
**Warning signs:** API JSON exposes `total_token_estimate`, `token_budget`, or raw evidence scores.

## Code Examples

Verified current boundary and reuse points:

### Phase 3 synthesis boundary already exists
```python
# Source: skill/retrieval/orchestrate.py
evidence_pack = build_evidence_pack(...)
return _shape_response(
    plan=plan,
    outcome=outcome,
    evidence_pack=evidence_pack,
)
```

### Public canonical-evidence surface already preserves retained slices
```python
# Source: skill/api/schema.py
class RetrieveCanonicalEvidenceItem(BaseModel):
    evidence_id: str
    canonical_title: str
    canonical_url: str
    retained_slices: list[RetrieveRetainedSliceItem]
```

These two facts mean Phase 4 can be planned as an answer layer over an existing bounded, structured evidence surface rather than another retrieval redesign.

## State of the Art

| Old Approach | Recommended Phase 4 Approach | Impact |
|--------------|------------------------------|--------|
| Retrieval-only response | Separate answer endpoint backed by retrieval + synthesis orchestration | Clearer contracts and outcome states |
| Bare source links | Evidence-bound citations with `evidence_id` and `source_record_id` | Directly improves traceability |
| Model output trusted as-is | Post-generation citation checker and deterministic downgrade | Reduces hallucinated or dangling claims |
| Free-form caveats | Deterministic uncertainty notes from evidence facts | More honest, repeatable output |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Retained slices from Phase 3 are sufficient to support quote-level citations without fetching full documents in Phase 4. | Citation binding | If wrong, Phase 4 may need a new text-ingress layer before reliable quote validation. |
| A2 | A thin injectable model-client interface is enough to isolate MiniMax specifics from the rest of the synthesis code. | Generator architecture | If wrong, network/client concerns could leak into orchestration and tests. |
| A3 | Retrieval `partial` can still produce `grounded_success` when all surfaced claims are fully cited, with uncertainty notes carrying the partial-retrieval context. | Answer-state mapping | If wrong, the final state taxonomy may need stricter downgrade rules. |

## Open Questions (RESOLVED)

1. **Should final answer generation reuse `/retrieve` or get a dedicated endpoint?**
   - **Resolution:** Add a dedicated `/answer` endpoint.
   - **Why this resolves the question:** It keeps retrieval evidence contracts and final answer contracts separate while still reusing the same browser-free core.

2. **What is the minimum citation granularity needed for OUTP-02?**
   - **Resolution:** Use `evidence_id` plus `source_record_id`, with `quote_text` copied from or validated against retained slices.
   - **Why this resolves the question:** It is specific enough for traceability and already supported by Phase 3's retained-slice boundary.

3. **How should final answer state be decided?**
   - **Resolution:** `retrieval_failure` only when retrieval fails with no usable canonical evidence; `insufficient_evidence` when evidence exists but not every surfaced key point passes citation validation; `grounded_success` only when all surfaced key points are grounded.
   - **Why this resolves the question:** It cleanly separates system failure from honest insufficiency and from fully grounded success.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python | synthesis runtime | Yes | Local venv present | Native execution |
| pytest | Phase 4 tests | Yes | Repository already uses pytest | Reuse existing test setup |
| fastapi / pydantic | answer API layer | Yes | Already in repo environment | Extend current API modules |
| MiniMax client wrapper | structured generation | No repo wrapper yet | N/A | Create thin injectable interface; tests use fake client |

**Missing dependencies with no fallback:**
- No live MiniMax wrapper exists in the repo today. Execution should create one that is injectable and testable without network access.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none - use environment guard for plugin isolation |
| Quick run command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py tests/test_answer_citation_check.py -q` |
| Full suite command | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` |
| Estimated runtime | ~25-35 seconds once Phase 4 tests exist |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTP-01 | Structured answer always includes conclusion, key points, source links, and uncertainty or gaps | unit + integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q` | No - Wave 0 |
| OUTP-02 | Each key factual claim is bound to at least one valid evidence citation | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_citation_check.py tests/test_answer_generator.py -q` | No - Wave 0 |
| OUTP-03 | Final response distinguishes grounded success, insufficient evidence, and retrieval failure | unit + integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_state_mapping.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** Run the smallest relevant Phase 4 test file(s) plus any touched integration file.
- **Per plan wave:** Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`.
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/fixtures/answer_phase4_cases.json` - grounded, insufficient, and retrieval-failure answer fixtures
- [ ] `tests/test_answer_contracts.py` - answer contract and required-field regressions
- [ ] `tests/test_answer_state_mapping.py` - retrieval-to-answer state rules
- [ ] `tests/test_answer_generator.py` - prompt/JSON parse behavior with fake model client
- [ ] `tests/test_answer_citation_check.py` - citation-binding and fail-closed validation
- [ ] `tests/test_answer_integration.py` - retrieve -> synthesize -> validate orchestration path
- [ ] `tests/test_api_answer_endpoint.py` - `/answer` endpoint response states and schema

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Yes | Parsed model output and answer API payloads must reject missing or extra fields. |
| V8 Data Protection | Yes | Retrieved evidence text remains inert data; never execute or obey instructions inside evidence content. |
| V10 Malicious Code | Indirectly | Generator and checker must treat all retrieved text and model output as untrusted until validated. |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection embedded in retained evidence slices | Elevation of Privilege | Prompt builder must frame evidence as quoted context only and generator results must be schema-validated. |
| Fabricated or dangling citations | Tampering | Citation checker validates `evidence_id`, `source_record_id`, and quote text against actual retained slices. |
| Retrieval-state confusion | Spoofing | Final answer state is derived deterministically from retrieval outcome plus citation-check results. |
| Budget telemetry leakage | Information Disclosure | Public answer schema exposes only structured answer data and high-level uncertainty, not raw internal counters. |

## Sources

### Primary (HIGH confidence)
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/PROJECT.md`
- `.planning/STATE.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/SUMMARY.md`
- `.planning/research/PITFALLS.md`
- `.planning/research/FEATURES.md`
- `.planning/phases/03-evidence-normalization-budgeted-context/03-RESEARCH.md`
- `.planning/phases/03-evidence-normalization-budgeted-context/03-VERIFICATION.md`
- `skill/api/entry.py`
- `skill/api/schema.py`
- `skill/retrieval/orchestrate.py`
- `skill/retrieval/models.py`
- `skill/evidence/models.py`

### Secondary (MEDIUM confidence)
- `claude/需求.md` - suggested output shape `{summary, key_points[], sources[], gaps[]}` aligned with the roadmap but not yet reflected in code.
- `.planning/phases/03-evidence-normalization-budgeted-context/03-03-PLAN.md`
- `.planning/phases/03-evidence-normalization-budgeted-context/03-05-PLAN.md`

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Current integration boundary and available evidence fields: HIGH - directly verified from the repo.
- Single-call structured synthesis pattern: HIGH - consistent with project architecture and contest direction.
- Answer-state mapping policy for retrieval `partial`: MEDIUM - coherent with current requirements, but still a project assumption until Phase 4 is executed.

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days)
