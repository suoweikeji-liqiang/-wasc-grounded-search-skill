---
phase: 04-grounded-structured-answer-generation
verified: 2026-04-12T09:09:07Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 4: Grounded Structured Answer Generation Verification Report

**Phase Goal:** Users can receive judge-optimized structured answers where factual claims are source-traceable and answer state is explicit.
**Verified:** 2026-04-12T09:09:07Z
**Status:** human_needed
**Re-verification:** Yes - after hardening the China MiniMax endpoint boundary and live-output parser tolerance

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Structured answer contracts always carry `conclusion`, `key_points`, `sources`, `uncertainty_notes`, and `gaps`, even when the final state is not grounded success. | VERIFIED | `skill/synthesis/models.py` defines `StructuredAnswerDraft` with all required fields; `skill/api/schema.py` defines strict `AnswerResponse`; `tests/test_answer_contracts.py` verifies required-field behavior. |
| 2 | Each key point citation binds to explicit `evidence_id` plus `source_record_id`, not bare links only. | VERIFIED | `ClaimCitation` and `AnswerCitationItem` require `evidence_id`, `source_record_id`, `source_url`, and `quote_text`; `tests/test_answer_contracts.py` enforces the field set. |
| 3 | Final answer state is explicit and distinct from retrieval status: `grounded_success`, `insufficient_evidence`, or `retrieval_failure`. | VERIFIED | `AnswerStatus` and `determine_answer_status(...)` encode the three-state taxonomy; `tests/test_answer_state_mapping.py` covers all three transitions. |
| 4 | A retrieval success cannot be exposed as grounded unless every surfaced key point is citation-backed. | VERIFIED | `validate_answer_citations(...)` counts grounded key points and `determine_answer_status(...)` downgrades incomplete grounding; `tests/test_answer_integration.py` exercises the downgrade path. |
| 5 | The generator produces strict structured answer drafts containing conclusion, key points, and citation payloads instead of free-form prose. | VERIFIED | `build_grounded_answer_prompt(...)` requires JSON-only output and `generate_answer_draft(...)` strictly parses the returned draft; `tests/test_answer_generator.py` covers the prompt contract and parse path. |
| 6 | Citation validation fails closed when a key point cites a missing `evidence_id`, a missing `source_record_id`, or a quote not supported by the retained slice text. | VERIFIED | `skill/synthesis/citation_check.py` rejects missing evidence IDs, dangling source-record IDs, and quote mismatches; `tests/test_answer_citation_check.py` covers all three failures. |
| 7 | Uncertainty notes are derived from clipping, retrieval gaps, heuristic academic matches, and incomplete policy metadata, not from arbitrary model hedging. | VERIFIED | `build_uncertainty_notes(...)` emits deterministic prefixes for each condition; `tests/test_answer_citation_check.py` asserts the required note prefixes. |
| 8 | A generated draft cannot graduate to grounded success unless the citation checker passes every returned key point. | VERIFIED | `execute_answer_pipeline(...)` computes `answer_status` from citation-check counts rather than raw generation output; `tests/test_answer_integration.py` proves citation failures downgrade to `insufficient_evidence`. |
| 9 | The browser-free retrieval core now feeds a final `/answer` path that returns conclusion, key points, sources, gaps, and uncertainty notes. | VERIFIED | `skill/api/entry.py` adds `/answer` on top of the existing browser-free route and retrieval plan builders; `tests/test_api_answer_endpoint.py` asserts the required response fields. |
| 10 | Only citation-checked key points can contribute to `grounded_success`; invalid or uncited claims degrade the final response to `insufficient_evidence`. | VERIFIED | `execute_answer_pipeline(...)` returns only `citation_result.validated_key_points` and rewrites the conclusion for insufficient-evidence cases; `tests/test_answer_integration.py` verifies the filtered response shape. |
| 11 | Users can clearly distinguish `grounded_success`, `insufficient_evidence`, and `retrieval_failure` in the API payload. | VERIFIED | `AnswerResponse` exposes `answer_status`; `tests/test_answer_state_mapping.py`, `tests/test_answer_integration.py`, and `tests/test_api_answer_endpoint.py` cover all three output states. |
| 12 | The public answer payload does not expose raw token budgets, evidence scores, or other internal telemetry from Phase 3. | VERIFIED | `AnswerResponse` omits internal budget/scoring fields; `tests/test_api_answer_endpoint.py` asserts `total_token_estimate` and `token_budget` are absent. |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `skill/synthesis/models.py` | Internal answer, citation, key-point, source, and draft contracts | VERIFIED | Declares `AnswerStatus`, `ClaimCitation`, `KeyPoint`, `SourceReference`, and `StructuredAnswerDraft`. |
| `skill/synthesis/state.py` | Deterministic retrieval-to-answer state mapping | VERIFIED | Exports `determine_answer_status(...)` with the required downgrade rules. |
| `skill/api/schema.py` | Public answer request/response schema | VERIFIED | Adds `AnswerRequest`, `AnswerResponse`, and strict nested citation/key-point/source models. |
| `tests/fixtures/answer_phase4_cases.json` | Grounded, insufficient, and retrieval-failure fixtures | VERIFIED | Contains the three named Phase 4 fixtures used by unit and integration coverage. |
| `skill/synthesis/prompt.py` | Prompt serialization for bounded canonical evidence | VERIFIED | Serializes evidence IDs, retained-slice IDs, and route metadata into the grounded prompt. |
| `skill/synthesis/generator.py` | MiniMax-compatible client boundary plus strict JSON parsing | VERIFIED | Implements `MiniMaxTextClient` against the official China OpenAI-compatible `/v1/chat/completions` shape and tolerates wrapped JSON plus advisory-field drift without weakening citation checks. |
| `skill/synthesis/citation_check.py` | Fail-closed validation of answer citations | VERIFIED | Exports `validate_answer_citations(...)` and `CitationCheckResult`. |
| `skill/synthesis/uncertainty.py` | Deterministic uncertainty-note builder | VERIFIED | Emits note prefixes from observable retrieval/evidence conditions. |
| `skill/synthesis/orchestrate.py` | Retrieve -> synthesize -> validate -> answer pipeline | VERIFIED | Rehydrates canonical evidence, short-circuits retrieval failure, and shapes the final answer payload. |
| `skill/api/entry.py` | Browser-free `/answer` endpoint | VERIFIED | Wires classification, retrieval-plan building, and `execute_answer_pipeline(...)` into FastAPI. |
| `tests/test_answer_integration.py` | End-to-end synthesis orchestration regressions | VERIFIED | Exercises grounded-success, insufficient-evidence, and retrieval-failure orchestration behavior. |
| `tests/test_api_answer_endpoint.py` | API-level answer endpoint regressions | VERIFIED | Covers all three answer states and verifies public-field omissions. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `skill/synthesis/models.py` | `skill/evidence/models.py` | evidence-bound citation identifiers | WIRED | Phase link verification found `evidence_id`, `source_record_id`, and `quote_text` patterns in the synthesis contract layer. |
| `skill/synthesis/state.py` | `skill/retrieval/models.py` | retrieval-to-answer state translation | WIRED | Phase link verification found the retrieval-status patterns used by `determine_answer_status(...)`. |
| `skill/api/schema.py` | `skill/synthesis/models.py` | public answer payload uses the internal synthesis contract | WIRED | Phase link verification found the answer-model patterns on the schema boundary. |
| `skill/synthesis/prompt.py` | `skill/evidence/models.py` | prompt serialization of evidence IDs and retained slices | WIRED | Phase link verification found the retained-slice serialization patterns in the prompt builder. |
| `skill/synthesis/generator.py` | `skill/synthesis/models.py` | strict parse into answer draft contracts | WIRED | Phase link verification found `StructuredAnswerDraft`, `KeyPoint`, and `ClaimCitation` references in the generator. |
| `skill/synthesis/citation_check.py` | `skill/evidence/models.py` | validation of quote text against retained slice text | WIRED | Phase link verification found the evidence-bound citation patterns in the checker. |
| `skill/synthesis/orchestrate.py` | `skill/retrieval/orchestrate.py` | answer pipeline starts from `execute_retrieval_pipeline(...)` | WIRED | Phase link verification found the retrieval entrypoint reference in orchestration. |
| `skill/synthesis/orchestrate.py` | `skill/synthesis/citation_check.py` | citation validation gates final answer state | WIRED | Phase link verification found `validate_answer_citations(...)` on the orchestration path. |
| `skill/api/entry.py` | `skill/synthesis/orchestrate.py` | API answer path uses the synthesis orchestrator | WIRED | Phase link verification found `execute_answer_pipeline` and `/answer` wiring. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 4 answer suite stays green after MiniMax-client hardening | `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py tests/test_answer_generator.py tests/test_answer_citation_check.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q` | `30 passed in 0.80s` | PASS |
| Repository-wide suite stays green | `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q` | `127 passed in 1.35s` | PASS |
| Phase artifact gate | `node .../gsd-tools.cjs verify artifacts <04-0X-PLAN.md>` | `12/12` artifacts passed across plans `04-01`..`04-03` | PASS |
| Phase key-link gate | `node .../gsd-tools.cjs verify key-links <04-0X-PLAN.md>` | `9/9` key links verified across plans `04-01`..`04-03` | PASS |
| Post-execution schema drift gate | `node .../gsd-tools.cjs verify schema-drift 04` | `drift_detected: false` | PASS |
| Live MiniMax smoke through `/answer` | `.env`-backed `/answer` requests with the official China endpoint | Policy smoke returned HTTP 200 with `insufficient_evidence`; academic smoke returned HTTP 200 with `grounded_success`; both payloads preserved the required citation-field shape and no internal telemetry leaked | PASS |

## Requirements Coverage

| Requirement | Description | Status | Evidence |
| --- | --- | --- | --- |
| `OUTP-01` | User can receive a structured result containing a conclusion, key points, source links, and uncertainty or gaps. | SATISFIED | `AnswerResponse` enforces the response shape, `/answer` exposes it, and endpoint tests assert the required fields. |
| `OUTP-02` | User can trace each key factual claim back to at least one cited source or quoted evidence unit. | SATISFIED | Citation contracts require evidence and retained-slice identifiers, and the citation checker rejects dangling or unsupported claims. |
| `OUTP-03` | User can distinguish between retrieval failure, insufficient evidence, and successful grounded answers. | SATISFIED | `AnswerStatus`, orchestration mapping, and endpoint/integration tests cover all three final states. |

## Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `tests/test_answer_contracts.py` | `OUTP-01`, `OUTP-02` | Yes | 0 | No | Value | PASS |
| `tests/test_answer_state_mapping.py` | `OUTP-03` | Yes | 0 | No | Value | PASS |
| `tests/test_answer_generator.py` | `OUTP-01`, `OUTP-02` | Yes | 0 | No | Value | PASS |
| `tests/test_answer_citation_check.py` | `OUTP-02`, `OUTP-03` | Yes | 0 | No | Value | PASS |
| `tests/test_answer_integration.py` | `OUTP-01`, `OUTP-02`, `OUTP-03` | Yes | 0 | No | Behavioral | PASS |
| `tests/test_api_answer_endpoint.py` | `OUTP-01`, `OUTP-03` | Yes | 0 | No | Behavioral | PASS |

- Disabled requirement-linked tests: 0
- Circular fixture-generation patterns found in the linked test set: 0
- Insufficient assertion-strength findings: 0

## Anti-Patterns Found

None confirmed. Targeted scans across the Phase 4 source and test files found no `TODO`, `FIXME`, `HACK`, placeholder, or skipped-test markers in the reviewed file set.

## Human Verification Required

### 1. Conclusion Honesty Across Outcome States
**Test:** Review one real grounded-success response, one insufficient-evidence response, and one retrieval-failure response from the live model-backed endpoint.
**Expected:** The conclusion language matches `answer_status`, uncertainty notes stay honest, and unsupported claims are not overstated.
**Why human:** The final wording is model-authored and requires semantic judgment, not just schema validation.

## Gaps Summary

**No automated or code-level gaps found.** Phase 4's planned must-haves are implemented, wired, and covered by passing tests.

Phase completion is still waiting on one human check:

1. Human judgment over conclusion honesty across the answer states.

## Verification Metadata

**Verification approach:** Goal-backward, using Phase 4 ROADMAP success criteria plus all plan-declared must-haves
**Must-haves source:** `04-01-PLAN.md`, `04-02-PLAN.md`, `04-03-PLAN.md`, and `.planning/ROADMAP.md`
**Artifact checks:** `12/12` plan-declared artifacts passed via `gsd-tools verify artifacts`
**Link checks:** `9/9` plan-declared key links verified via `gsd-tools verify key-links`
**Automated checks:** Phase 4 answer suite passed (`30 passed in 0.80s`); repository-wide suite passed (`127 passed in 1.35s`)
**Code review:** `04-REVIEW.md` status `clean`
**Schema drift gate:** `drift_detected: false`
**Human checks required:** `1`

---

_Verified: 2026-04-12T09:09:07Z_
_Verifier: Codex (manual goal-backward verification refresh)_
