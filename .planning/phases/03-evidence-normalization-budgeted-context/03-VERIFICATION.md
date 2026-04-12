---
phase: 03-evidence-normalization-budgeted-context
verified: 2026-04-12T07:40:12Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 3: Evidence Normalization & Budgeted Context Verification Report

**Phase Goal:** Users can get clean, consolidated evidence sets with domain-specific metadata quality and bounded context size.
**Verified:** 2026-04-12T07:40:12Z
**Status:** passed
**Re-verification:** Yes - after executing gap-closure plans `03-04` and `03-05`

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | User can receive answers based on evidence that has been deduplicated and reranked before synthesis. | VERIFIED | `skill/retrieval/orchestrate.py` now runs `prioritize -> normalize -> collapse -> score -> pack` and shapes both `results` and `canonical_evidence` from `EvidencePack.canonical_evidence`; `tests/test_retrieval_integration.py` covers the real runtime path; fresh suite result: `97 passed in 1.26s`. |
| 2 | User can see policy evidence annotated with authority plus effective/publication date and jurisdiction/version when available. | VERIFIED | Live policy spot-check through `policy_search -> normalize_hit_candidates -> collapse_evidence_records` produced canonical policy records with authority, dates, `version_status`, and `jurisdiction_status`; `tests/test_evidence_runtime_integration.py` and `tests/test_retrieval_integration.py` pin the behavior. |
| 3 | User can receive academic evidence where duplicate/preprint/published variants are normalized into canonical citations. | VERIFIED | Live Semantic Scholar plus arXiv spot-check yielded `canonical_count: 1` with DOI, arXiv ID, `evidence_level: peer_reviewed`, and linked `preprint` variant; `tests/test_evidence_runtime_integration.py` and `tests/test_retrieval_integration.py` exercise the real merge path. |
| 4 | User can receive outputs built from a bounded top-K evidence set that controls token usage. | VERIFIED | `skill/evidence/pack.py` still enforces hard token budgets and top-K; runtime spot-check with `token_budget=12, top_k=1` produced `canonical_count: 1` with `clipped: True`; outward API still exposes only `evidence_clipped` and `evidence_pruned`. |
| 5 | Phase 3 keeps raw retrieval records and normalized canonical evidence records side by side instead of replacing raw hits. | VERIFIED | `skill/evidence/models.py` keeps `CanonicalEvidence.raw_records` and `EvidencePack.raw_records` alongside `canonical_evidence`; `tests/test_evidence_models.py` confirms raw and canonical records remain available together. |
| 6 | Canonical evidence is document-oriented with retained slices, not slice-only and not document-only. | VERIFIED | `CanonicalEvidence` requires document-level identity plus `retained_slices`, capped at two by default; `tests/test_evidence_models.py` validates the contract and immutability. |
| 7 | Policy records cannot silently hide missing `version` or `jurisdiction`; explicit status markers are required. | VERIFIED | `skill/evidence/models.py` enforces `version_status` and `jurisdiction_status`; `skill/evidence/normalize.py` derives them from observed hit values; `tests/test_evidence_policy.py` and `tests/test_evidence_runtime_integration.py` cover observed, inferred, and missing states. |
| 8 | Academic canonicalization must distinguish strong ID matches from heuristic merges and preserve linked variants. | VERIFIED | `skill/evidence/academic.py` differentiates strong-ID vs heuristic groups and emits `linked_variants`; `tests/test_evidence_academic.py` covers strong-ID, heuristic-only, and mixed-confidence merges. |
| 9 | Policy canonicalization uses version/date-aware document identity and explicit metadata-status handling instead of URL-only dedupe. | VERIFIED | `skill/evidence/policy.py` groups on authority/title plus shared version or date identity and keeps explicit metadata status markers; `tests/test_evidence_policy.py` verifies duplicate collapse and minimum metadata handling. |
| 10 | Academic canonicalization uses DOI > arXiv ID > title+first_author+year and marks heuristic merges explicitly. | VERIFIED | `skill/evidence/academic.py` uses DOI first, then arXiv, then title-author-year aliases, with `canonical_match_confidence` carried through; `tests/test_evidence_academic.py` verifies the precedence and fallback rules. |
| 11 | Industry duplicates are merged conservatively and complementary metadata is folded into the canonical record rather than discarded. | VERIFIED | `skill/evidence/dedupe.py` requires same-host plus high title and snippet similarity before merging, then folds complementary scalar metadata into the canonical record; `tests/test_evidence_dedupe.py` covers merge and over-merge rejection. |
| 12 | Evidence packing enforces a hard token budget and top-K ceiling rather than fixed K alone. | VERIFIED | `skill/evidence/pack.py` performs top-K selection, token accounting, slice trimming, and record dropping; `tests/test_evidence_pack.py` verifies budget clipping and top-K enforcement. |
| 13 | Mixed queries preserve primary-route dominance but reserve a small minimum share for supplemental evidence. | VERIFIED | `_select_top_k(...)` reserves supplemental slots when both route roles are present; `tests/test_evidence_pack.py` proves a supplemental record survives mixed-route packing. |
| 14 | Over-budget trimming removes low-scoring slices before dropping whole documents. | VERIFIED | `_trim_lowest_scoring_slice(...)` runs before `_drop_lowest_scoring_record(...)`; `tests/test_evidence_pack.py` verifies slice-first pruning and high-value record retention. |
| 15 | External response surfaces expose whether clipping happened without leaking internal budget accounting. | VERIFIED | `RetrieveResponse` exposes only `canonical_evidence`, `evidence_clipped`, and `evidence_pruned`; `tests/test_retrieval_integration.py` asserts budget counters such as `token_budget` and `total_token_estimate` never appear in the payload. |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `skill/evidence/models.py` | Raw and canonical evidence contracts with provenance, retained slices, and metadata status fields | VERIFIED | Frozen dataclasses enforce policy and academic invariants while keeping raw hit provenance attached. |
| `skill/evidence/normalize.py` | Runtime normalization ingress from `RetrievalHit` to `RawEvidenceRecord` | VERIFIED | Maps observed policy and academic fields directly from live hits and derives only policy completeness markers. |
| `skill/evidence/policy.py` | Policy canonicalization with explicit metadata-status handling | VERIFIED | Canonicalizes policy records using authority-plus-date identity and keeps explicit version/jurisdiction status outputs. |
| `skill/evidence/academic.py` | Academic canonicalization with strong-ID and heuristic merge paths | VERIFIED | Canonicalizes DOI/arXiv/title-author-year groups and emits linked variants with confidence markers. |
| `skill/evidence/dedupe.py` | Domain-aware duplicate-collapse orchestrator | VERIFIED | Routes policy, academic, and industry records to domain-specific collapse paths without dropping raw provenance. |
| `skill/evidence/score.py` | Deterministic evidence scoring | VERIFIED | Produces stable total scores from route role, metadata completeness, authority, and retained-slice strength. |
| `skill/evidence/pack.py` | Hard-budget evidence packing | VERIFIED | Enforces top-K, token budget, supplemental reserve, and slice-first clipping. |
| `skill/retrieval/models.py` | Retrieval contract with observed policy and academic metadata | VERIFIED | `RetrievalHit` now includes authority, date, version, DOI, arXiv, author, year, and evidence-level fields. |
| `skill/retrieval/orchestrate.py` | Retrieval integration to the canonical evidence pack | VERIFIED | Shapes `results` and additive `canonical_evidence` from `EvidencePack.canonical_evidence` instead of raw prioritized hits. |
| `skill/api/schema.py` | Public retrieval schema for bounded canonical evidence | VERIFIED | Adds canonical evidence, retained slices, linked variants, and budget clip/prune flags without exposing raw token counters. |
| `tests/test_evidence_models.py` | Contract regressions for raw/canonical evidence structure | VERIFIED | Covers provenance retention, immutability, retained-slice limits, and `EvidencePack` shape. |
| `tests/test_evidence_runtime_integration.py` | Real-path policy and academic normalization regressions | VERIFIED | Uses the live `normalize_hit_candidates(...)` and `collapse_evidence_records(...)` path with no normalization monkeypatches. |
| `tests/test_retrieval_integration.py` | End-to-end retrieval runtime and API contract regressions | VERIFIED | Exercises the real `normalize -> collapse -> score -> pack -> response` path by stubbing only `run_retrieval(...)`. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `skill/evidence/models.py` | `skill/retrieval/models.py` | raw retrieval hit provenance | WIRED | `RawEvidenceRecord.raw_hit` stores the original `RetrievalHit`, preserving retrieval-layer provenance. |
| `skill/evidence/normalize.py` | `skill/retrieval/priority.py` | prioritized hits become normalization ingress | WIRED | `execute_retrieval_pipeline(...)` prioritizes live hits before calling `normalize_hit_candidates(...)`. |
| `skill/evidence/dedupe.py` | `skill/evidence/policy.py` | policy canonicalization branch | WIRED | Policy raw records are routed through `canonicalize_policy_records(...)`. |
| `skill/evidence/dedupe.py` | `skill/evidence/academic.py` | academic canonicalization branch | WIRED | Academic raw records are routed through `canonicalize_academic_records(...)`. |
| `skill/evidence/dedupe.py` | `skill/evidence/models.py` | canonical evidence output | WIRED | Duplicate collapse returns `CanonicalEvidence` records that preserve raw-record provenance. |
| `skill/evidence/pack.py` | `skill/evidence/dedupe.py` | canonical evidence ingress | WIRED | `build_evidence_pack(...)` consumes the collapsed and scored canonical evidence set. |
| `skill/retrieval/orchestrate.py` | `skill/evidence/pack.py` | post-priority evidence pack generation | WIRED | Orchestration passes scored canonical records into `build_evidence_pack(...)` on the live runtime path. |
| `skill/api/schema.py` | `skill/retrieval/orchestrate.py` | bounded canonical evidence and clip-state response contract | WIRED | `RetrieveResponse` receives additive canonical evidence plus clip/prune flags from orchestration. |
| `skill/retrieval/adapters/policy_official_registry.py` | `skill/retrieval/models.py` | `RetrievalHit` policy metadata fields | WIRED | Live policy adapters now emit authority, jurisdiction, dates, and version into `RetrievalHit`. |
| `skill/retrieval/adapters/academic_semantic_scholar.py` | `skill/evidence/normalize.py` | scholarly identifiers mapped into `RawEvidenceRecord` | WIRED | Semantic Scholar and arXiv metadata now reach normalization and downstream canonicalization. |
| `skill/evidence/normalize.py` | `skill/evidence/dedupe.py` | populated `RawEvidenceRecord` inputs for policy and academic canonicalizers | WIRED | Policy and academic canonicalizers now receive the metadata they require on the live path. |
| `tests/test_retrieval_integration.py` | `skill/retrieval/orchestrate.py` | real-path runtime assertions on `execute_retrieval_pipeline(...)` | WIRED | The integration suite verifies the bounded canonical pack is the outward response boundary. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Repository-wide test suite stays green after gap closure | `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest tests -q` | `97 passed in 1.26s` | PASS |
| Live policy normalization yields canonical policy evidence with explicit metadata statuses | Python spot-check: `policy_search -> normalize_hit_candidates -> collapse_evidence_records` | Canonical policy records returned with authority, publication/effective dates, `version_status`, and `jurisdiction_status` populated | PASS |
| Live academic normalization merges published and preprint variants | Python spot-check: Semantic Scholar + arXiv hits through the real normalize/collapse path | `canonical_count: 1`, DOI and arXiv ID preserved, linked `preprint` variant emitted, `match_confidence: heuristic` | PASS |
| Pack builder enforces a bounded output set | Python spot-check: `build_evidence_pack(..., token_budget=12, top_k=1)` | `canonical_count: 1`, `clipped: True`, `pruned: False`, `total_token_estimate: 6` | PASS |
| Post-execution schema drift gate | `node .../gsd-tools.cjs verify schema-drift 03` | `drift_detected: false` | PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `EVID-01` | `03-01`, `03-02`, `03-03`, `03-05` | User can receive answers whose cited evidence is deduplicated and reranked before synthesis. | SATISFIED | Runtime orchestration now shapes outward evidence from the canonical pack, and runtime integration tests cover the full evidence path. |
| `EVID-02` | `03-01`, `03-02`, `03-04` | User can receive policy answers that include authority, dates, and version or jurisdiction when available. | SATISFIED | Live policy adapters emit metadata, normalization preserves it, and canonical policy records retain explicit status markers. |
| `EVID-03` | `03-01`, `03-02`, `03-04` | User can receive academic answers that normalize duplicate/preprint/published records into a canonical citation set. | SATISFIED | Live scholarly identifiers now reach canonicalization, and the published plus preprint runtime spot-check collapses to one canonical record. |
| `EVID-04` | `03-03`, `03-05` | User can receive answers that keep only a bounded top-K evidence set to control token cost. | SATISFIED | `build_evidence_pack(...)` enforces the hard cap and the public API exposes only bounded canonical evidence with clip/prune signals. |

## Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `tests/test_evidence_models.py` | `EVID-01`, `EVID-02`, `EVID-03` | Yes | 0 | No | Value | PASS |
| `tests/test_evidence_policy.py` | `EVID-02` | Yes | 0 | No | Value | PASS |
| `tests/test_evidence_academic.py` | `EVID-03` | Yes | 0 | No | Value | PASS |
| `tests/test_evidence_dedupe.py` | `EVID-01` | Yes | 0 | No | Behavioral | PASS |
| `tests/test_evidence_pack.py` | `EVID-01`, `EVID-04` | Yes | 0 | No | Behavioral | PASS |
| `tests/test_evidence_runtime_integration.py` | `EVID-01`, `EVID-02`, `EVID-03` | Yes | 0 | No | Behavioral | PASS |
| `tests/test_retrieval_integration.py` | `EVID-01`, `EVID-04` | Yes | 0 | No | Behavioral | PASS |

- Disabled requirement-linked tests: 0
- Circular expected-value generators or snapshot-capture helpers found in the linked test set: 0
- Insufficient assertion-strength findings: 0

## Anti-Patterns Found

None confirmed. Targeted scans across the Phase 3 source and test files found no `TODO`, `FIXME`, `HACK`, placeholder, or skipped-test markers in the reviewed file set.

## Human Verification Required

None - all Phase 3 goal truths were verifiable programmatically from the codebase, the repository-wide test suite, and direct runtime spot-checks.

## Gaps Summary

**No gaps found.** The previously failing live-path issues are now closed:

- policy metadata reaches canonicalization and survives with explicit missing-status markers
- academic published and preprint variants merge into a canonical citation set on the live path
- outward retrieval responses now use the bounded canonical evidence pack instead of raw prioritized hits

Phase 3 goal achieved. Ready to proceed.

## Verification Metadata

**Verification approach:** Goal-backward, using Phase 3 ROADMAP success criteria plus all plan-declared must-haves
**Must-haves source:** `03-01-PLAN.md` through `03-05-PLAN.md` frontmatter and `.planning/ROADMAP.md`
**Artifact checks:** `19/19` plan-declared artifacts passed via `gsd-tools verify artifacts`
**Link checks:** `15/15` plan-declared key links verified via `gsd-tools verify key-links`
**Automated checks:** repository-wide pytest suite passed (`97 passed in 1.26s`)
**Runtime spot-checks:** `4/4` passed
**Schema drift gate:** `drift_detected: false`
**Human checks required:** `0`

---

_Verified: 2026-04-12T07:40:12Z_
_Verifier: Codex (manual goal-backward re-verification)_
