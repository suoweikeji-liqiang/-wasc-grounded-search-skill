---
phase: 03-evidence-normalization-budgeted-context
verified: 2026-04-12T02:22:01Z
status: gaps_found
score: 11/15 must-haves verified
overrides_applied: 0
gaps:
  - truth: "User can receive answers based on evidence that has been deduplicated and reranked before synthesis."
    status: failed
    reason: "The runtime path computes canonicalization and packing, but live policy hits are dropped for missing metadata, live academic hits stay split by source, and the outward response still uses prioritized raw hits."
    artifacts:
      - path: "skill/evidence/normalize.py"
        issue: "build_raw_record leaves policy authority/date/version fields and academic DOI/arXiv/author/year fields empty for live retrieval hits."
      - path: "skill/retrieval/orchestrate.py"
        issue: "_shape_response returns prioritized_hits rather than the canonical evidence pack."
    missing:
      - "Populate policy and academic metadata on RawEvidenceRecord from live retrieval hits or adapter payloads before duplicate collapse."
      - "Hand off EvidencePack.canonical_evidence to the synthesis/output boundary instead of discarding it after clipping is computed."
  - truth: "User can see policy evidence annotated with authority plus effective/publication date and jurisdiction/version when available."
    status: failed
    reason: "Policy canonicalization requires authority and at least one date, but live normalization never provides them, so runtime policy canonicalization returns no records."
    artifacts:
      - path: "skill/evidence/normalize.py"
        issue: "Policy raw records are created with authority=None, publication_date=None, effective_date=None, version=None."
      - path: "skill/evidence/policy.py"
        issue: "canonicalize_policy_records filters out any record missing authority or both date fields."
    missing:
      - "Add runtime extraction or adapter-level population for authority, publication/effective dates, version, and jurisdiction before policy canonicalization."
  - truth: "User can receive academic evidence where duplicate/preprint/published variants are normalized into canonical citations."
    status: failed
    reason: "Academic canonicalization logic exists, but the live normalization path never sets DOI, arXiv ID, first author, year, or evidence level, so duplicate/preprint pairs remain separate source-keyed records."
    artifacts:
      - path: "skill/evidence/normalize.py"
        issue: "Academic raw records are created with doi=None, arxiv_id=None, first_author=None, year=None, evidence_level=None."
      - path: "skill/evidence/academic.py"
        issue: "_academic_aliases falls back to source_id+url when scholarly identifiers are absent, preventing canonical merges."
    missing:
      - "Populate DOI/arXiv/first_author/year/evidence_level for live academic hits before canonicalization."
      - "Add an integration test that runs the real normalization and academic canonicalization path without monkeypatching."
  - truth: "User can receive outputs built from a bounded top-K evidence set that controls token usage."
    status: failed
    reason: "build_evidence_pack enforces budget and top-K internally, but the outward retrieval response still returns prioritized_hits, not the bounded canonical evidence set."
    artifacts:
      - path: "skill/evidence/pack.py"
        issue: "The pack builder returns bounded canonical_evidence correctly, but no consumer uses that bounded set."
      - path: "skill/retrieval/orchestrate.py"
        issue: "The response is shaped from prioritized_hits and only forwards evidence_pack.clipped."
      - path: "skill/api/schema.py"
        issue: "The response contract exposes a clip flag but no bounded evidence payload or internal handoff object."
    missing:
      - "Use the bounded canonical evidence pack as the source for synthesis/output state."
      - "If the pack remains internal, thread it to the downstream synthesis boundary instead of rebuilding outward results from raw prioritized hits."
---

# Phase 3: Evidence Normalization & Budgeted Context Verification Report

**Phase Goal:** Users can get clean, consolidated evidence sets with domain-specific metadata quality and bounded context size.
**Verified:** 2026-04-12T02:22:01Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | User can receive answers based on evidence that has been deduplicated and reranked before synthesis. | FAILED | Live policy normalization produced `canonical_count: 0`; live academic normalization produced `canonical_count: 2` with no linked variants; outward response still uses `prioritized_hits` in `skill/retrieval/orchestrate.py:36-53,81-98`. |
| 2 | User can see policy evidence annotated with authority plus effective/publication date and jurisdiction/version when available. | FAILED | `skill/evidence/normalize.py:25-47` sets policy metadata to `None`; `skill/evidence/policy.py:129-133` drops records missing authority or dates. |
| 3 | User can receive academic evidence where duplicate/preprint/published variants are normalized into canonical citations. | FAILED | `skill/evidence/normalize.py:25-47` leaves scholarly identifiers empty; `skill/evidence/academic.py:29-46` falls back to source aliases, and the runtime spot-check returned two separate canonicals. |
| 4 | User can receive outputs built from a bounded top-K evidence set that controls token usage. | FAILED | `skill/evidence/pack.py:132-176` builds a bounded pack, but `skill/retrieval/orchestrate.py:93-98` returns raw prioritized hits instead of the pack contents. |
| 5 | Phase 3 keeps raw retrieval records and normalized canonical evidence records side by side instead of replacing raw hits. | VERIFIED | `skill/evidence/models.py:93-187` keeps `CanonicalEvidence.raw_records` and `EvidencePack.raw_records` alongside `canonical_evidence`; `tests/test_evidence_models.py:195-251` verifies both stay present. |
| 6 | Canonical evidence is document-oriented with retained slices, not slice-only and not document-only. | VERIFIED | `skill/evidence/models.py:93-136` defines `raw_records` plus `retained_slices` and enforces a two-slice default cap; `tests/test_evidence_models.py:113-192` covers immutability and slice limits. |
| 7 | Policy records cannot silently hide missing `version` or `jurisdiction`; explicit status markers are required. | VERIFIED | `skill/evidence/models.py:138-156` requires `version_status` and `jurisdiction_status`; `tests/test_evidence_policy.py:138-219` exercises both failure and success cases. |
| 8 | Academic canonicalization must distinguish strong ID matches from heuristic merges and preserve linked variants. | VERIFIED | `skill/evidence/academic.py:124-197` computes confidence and linked variants; `tests/test_evidence_academic.py:166-234` verifies strong-ID and heuristic paths. |
| 9 | Policy canonicalization uses version/date-aware document identity and explicit metadata-status handling instead of URL-only dedupe. | VERIFIED | `skill/evidence/policy.py:25-36,87-123` groups on authority/title plus shared version/publication/effective date and preserves status markers. |
| 10 | Academic canonicalization uses DOI > arXiv ID > title+first_author+year and marks heuristic merges explicitly. | VERIFIED | `skill/evidence/academic.py:29-46,106-159,162-197` implements the identifier priority and heuristic fallback behavior. |
| 11 | Industry duplicates are merged conservatively and complementary metadata is folded into the canonical record rather than discarded. | VERIFIED | `skill/evidence/dedupe.py:48-63,92-122,125-162` requires same-host high similarity and merges complementary scalar metadata; `tests/test_evidence_dedupe.py:67-132` covers merge and over-merge rejection. |
| 12 | Evidence packing enforces a hard token budget and top-K ceiling rather than fixed K alone. | VERIFIED | `skill/evidence/pack.py:25-61,132-176` applies top-K selection plus a hard token budget; `tests/test_evidence_pack.py:151-191` verifies clipping under budget pressure. |
| 13 | Mixed queries preserve primary-route dominance but reserve a small minimum share for supplemental evidence. | VERIFIED | `skill/evidence/pack.py:34-42` reserves supplemental slots; `tests/test_evidence_pack.py:194-237` verifies one supplemental record is preserved. |
| 14 | Over-budget trimming removes low-scoring slices before dropping whole documents. | VERIFIED | `skill/evidence/pack.py:64-94,151-163` trims low-scoring slices before record removal; `tests/test_evidence_pack.py:151-191` pins the slice-first behavior. |
| 15 | External response surfaces expose whether clipping happened without leaking internal budget accounting. | VERIFIED | `skill/api/schema.py:101-114` exposes only `evidence_clipped`; `tests/test_retrieval_integration.py:212-257` confirms token counters are absent from the API payload. |

**Score:** 11/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `skill/evidence/models.py` | Raw/canonical evidence contracts with provenance and metadata status fields | VERIFIED | Substantive dataclasses exist, are frozen, and enforce policy/academic invariants. |
| `skill/evidence/normalize.py` | Raw-hit normalization ingress | HOLLOW | Exists and is wired, but `build_raw_record` leaves policy and academic metadata empty in the live path. |
| `tests/fixtures/evidence_phase3_cases.json` | Deterministic policy/academic/mixed-route fixtures | VERIFIED | Fixture contains explicit policy status fields, academic IDs, and mixed-route cases. |
| `tests/test_evidence_models.py` | Contract regressions for raw/canonical separation | VERIFIED | Covers provenance, immutability, retained-slice limits, and EvidencePack shape. |
| `skill/evidence/policy.py` | Policy canonicalization with explicit metadata handling | HOLLOW | Canonicalization logic is substantive, but it receives no authority/date metadata from the live normalization path. |
| `skill/evidence/academic.py` | Academic canonicalization with linked variants | HOLLOW | Canonicalization logic is substantive, but live records lack DOI/arXiv/author/year inputs. |
| `skill/evidence/dedupe.py` | Domain-aware duplicate collapse orchestrator | HOLLOW | Wired to policy/academic/industry branches, but policy/academic branches are starved by upstream empty metadata. |
| `tests/test_evidence_dedupe.py` | Regressions for metadata merge and conservative industry dedupe | VERIFIED | Tests pass, but they use enriched records instead of the live normalization output. |
| `skill/evidence/score.py` | Deterministic evidence scoring | VERIFIED | Scores canonical records deterministically using route role, completeness, authority, and slice scores. |
| `skill/evidence/pack.py` | Budgeted evidence pack builder | VERIFIED | Enforces top-K, token budget, supplemental reserve, and slice-first pruning on canonical inputs. |
| `tests/test_evidence_pack.py` | Budget/cap/pruning regressions | VERIFIED | Covers ranking, top-K, slice-first pruning, and mixed-route reserve behavior. |
| `skill/retrieval/orchestrate.py` | Retrieval integration to normalized evidence pack | HOLLOW | Calls normalize/collapse/score/pack, but discards the bounded `canonical_evidence` and shapes output from raw prioritized hits. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `skill/evidence/models.py` | `skill/retrieval/models.py` | raw retrieval hit provenance | WIRED | `RawEvidenceRecord.raw_hit` stores `RetrievalHit` directly in `skill/evidence/models.py:33-54`. |
| `skill/evidence/normalize.py` | `skill/retrieval/priority.py` | prioritized hits become normalization ingress | WIRED | `skill/retrieval/orchestrate.py:75-84` calls `prioritize_hits(...)` then `normalize_hit_candidates(...)`. |
| `tests/test_evidence_policy.py` | `skill/evidence/models.py` | explicit metadata status checks | WIRED | `tests/test_evidence_policy.py:138-219` exercises `CanonicalEvidence` policy validation rules. |
| `skill/evidence/dedupe.py` | `skill/evidence/policy.py` | policy canonicalization branch | WIRED | `skill/evidence/dedupe.py:156-159` routes policy records to `canonicalize_policy_records(...)`. |
| `skill/evidence/dedupe.py` | `skill/evidence/academic.py` | academic canonicalization branch | WIRED | `skill/evidence/dedupe.py:156-159` routes academic records to `canonicalize_academic_records(...)`. |
| `skill/evidence/dedupe.py` | `skill/evidence/models.py` | `CanonicalEvidence` output | WIRED | `skill/evidence/dedupe.py:92-122,140-162` builds `CanonicalEvidence` outputs for each domain. |
| `skill/evidence/pack.py` | `skill/evidence/dedupe.py` | canonical evidence ingress | WIRED | `skill/retrieval/orchestrate.py:85-88` passes deduped canonicals into `build_evidence_pack(...)`. |
| `skill/retrieval/orchestrate.py` | `skill/evidence/pack.py` | post-priority evidence pack generation | WIRED | `skill/retrieval/orchestrate.py:85-92` computes and packs canonical evidence after scoring. |
| `skill/api/schema.py` | `skill/retrieval/orchestrate.py` | clipping indicator exposure without raw budget internals | WIRED | `RetrieveResponse.evidence_clipped` in `skill/api/schema.py:101-114` is set from `evidence_pack.clipped` in `skill/retrieval/orchestrate.py:93-98`. |
| `skill/evidence/normalize.py` | `skill/evidence/policy.py` | populated policy authority/date/version fields | NOT_WIRED | No live code populates `authority`, `publication_date`, `effective_date`, or `version` before `canonicalize_policy_records(...)` filters inputs. |
| `skill/evidence/normalize.py` | `skill/evidence/academic.py` | populated DOI/arXiv/author/year fields | NOT_WIRED | No live code populates `doi`, `arxiv_id`, `first_author`, `year`, or `evidence_level` before academic aliasing. |
| `skill/evidence/pack.py` | outward response/synthesis boundary | bounded canonical evidence payload | NOT_WIRED | `skill/retrieval/orchestrate.py:93-98` forwards only `evidence_pack.clipped`; `canonical_evidence` is discarded. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `skill/evidence/normalize.py` | `authority`, `publication_date`, `effective_date`, `version`, `doi`, `arxiv_id`, `first_author`, `year` | `RetrievalHit` fields in `skill/retrieval/models.py:16-29` plus `build_raw_record(...)` in `skill/evidence/normalize.py:18-47` | No | STATIC |
| `skill/evidence/policy.py` | `accepted_records` | `normalize_hit_candidates(...)` output filtered by `skill/evidence/policy.py:129-133` | No in live path | HOLLOW |
| `skill/evidence/academic.py` | `aliases` / canonical merge groups | `normalize_hit_candidates(...)` output passed through `skill/evidence/academic.py:29-46,203-223` | No in live path | HOLLOW |
| `skill/evidence/pack.py` | `working_records` / `canonical_evidence` | Canonical records from collapse/score routed by `skill/retrieval/orchestrate.py:85-92` | Yes, when canonical inputs exist | FLOWING |
| `skill/retrieval/orchestrate.py` | outward `results` | `prioritized_hits` via `_shape_results(...)`, not `evidence_pack.canonical_evidence` | No for normalized bounded evidence | DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 03 evidence tests pass | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py tests/test_evidence_policy.py tests/test_evidence_academic.py tests/test_evidence_dedupe.py tests/test_evidence_pack.py tests/test_retrieval_integration.py -q` | `27 passed in 0.76s` | PASS |
| Live policy normalization yields canonical policy evidence | Python snippet: `RetrievalHit -> normalize_hit_candidates -> collapse_evidence_records` with a policy hit | `{'raw_authority': None, 'raw_publication_date': None, 'raw_effective_date': None, 'raw_version_status': 'version_missing', 'raw_jurisdiction_status': 'jurisdiction_unknown', 'canonical_count': 0}` | FAIL |
| Live academic normalization merges published/preprint variants | Python snippet: published DOI hit + matching arXiv hit through the real normalize/collapse path | `{'record_alias_inputs': [(None, None, None, None), (None, None, None, None)], 'canonical_count': 2, 'evidence_ids': ['academic:source:94fe2ac4fb51', 'academic:source:d3a9875ff2e5'], 'linked_variant_counts': [0, 0]}` | FAIL |
| Pack builder enforces bounded canonical output | Python snippet: single canonical record through `build_evidence_pack(...)` with `token_budget=4, top_k=1` | `{'canonical_count': 1, 'total_token_estimate': 4, 'clipped': False}` | PASS |

### Requirements Coverage

All plan-declared Phase 3 requirement IDs are present in `.planning/REQUIREMENTS.md`. No orphaned Phase 3 requirements were found.

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `EVID-01` | `03-01`, `03-02`, `03-03` | User can receive answers whose cited evidence is deduplicated and reranked before synthesis. | BLOCKED | Collapse/score/pack modules exist, but live policy hits collapse to zero records, academic duplicates do not merge, and outward results still use raw prioritized hits. |
| `EVID-02` | `03-01`, `03-02` | User can receive policy answers that include source authority, effective date or publication date, and version or jurisdiction when available. | BLOCKED | `skill/evidence/normalize.py:25-47` never populates those fields; `skill/evidence/policy.py:129-133` drops such records at runtime. |
| `EVID-03` | `03-01`, `03-02` | User can receive academic answers that normalize duplicate/preprint/published records into a canonical citation set. | BLOCKED | `skill/evidence/normalize.py:25-47` leaves scholarly IDs empty; `skill/evidence/academic.py:44-46` falls back to source aliases, and the runtime spot-check produced two canonicals. |
| `EVID-04` | `03-03` | User can receive answers that keep only a bounded top-K evidence set to control token cost. | BLOCKED | `skill/evidence/pack.py:132-176` enforces the budget internally, but `skill/retrieval/orchestrate.py:93-98` does not use the bounded pack as output/handoff data. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `skill/evidence/normalize.py` | 34 | Hardcoded empty policy and academic metadata with no later live enrichment | Blocker | Policy canonicalization drops live records, and academic canonicalization cannot merge duplicate/preprint pairs. |
| `skill/retrieval/orchestrate.py` | 93 | Computed bounded evidence pack discarded except for `clipped` flag | Blocker | Outward results are not normalized, deduplicated, or top-K bounded. |
| `tests/test_retrieval_integration.py` | 62 | Monkeypatched fake normalize/collapse/score/pack pipeline | Warning | Integration tests miss the real runtime data-flow failures uncovered by direct spot-checks. |

### Gaps Summary

Phase 03 completed most of the lower-level contract and packing tasks, but the goal-backward check fails at the live runtime boundary. The codebase has strong internal dataclasses, canonicalizers, scoring, and pack selection, yet the runtime normalization step never enriches `RawEvidenceRecord` with the policy and academic metadata those canonicalizers depend on. That leaves live policy evidence empty and live academic duplicates unmerged.

The second blocker is the handoff boundary. `build_evidence_pack(...)` works on canonical inputs, but `execute_retrieval_pipeline(...)` shapes outward results from `prioritized_hits` and only forwards `evidence_clipped`. That means the user-visible retrieval output is still raw prioritized retrieval data rather than the clean, consolidated, bounded evidence set required by the Phase 3 roadmap contract.

No deferred later-phase match was found for these gaps. Phase 4 expects Phase 3 to have already produced usable normalized evidence; it does not explicitly cover backfilling metadata extraction or replacing the raw-hit response path with bounded canonical evidence.

---

_Verified: 2026-04-12T02:22:01Z_
_Verifier: Claude (gsd-verifier)_
