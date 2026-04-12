---
phase: 03-evidence-normalization-budgeted-context
plan: 04
subsystem: evidence
tags: [retrieval, normalization, policy, academic, pytest]
requires:
  - phase: 03-03
    provides: packed evidence pipeline hooks after normalization and duplicate collapse
provides:
  - observed metadata-bearing RetrievalHit records for policy and academic sources
  - raw evidence normalization that preserves live metadata and provenance
  - real-path runtime regressions for policy survival and academic variant merges
affects: [03-05, retrieval-orchestration, evidence-packing]
tech-stack:
  added: []
  patterns:
    - retrieval adapters emit observed metadata only; normalization derives completeness markers later
    - runtime regressions use the real normalize-plus-collapse path without monkeypatches
key-files:
  created:
    - tests/test_evidence_runtime_integration.py
    - .planning/phases/03-evidence-normalization-budgeted-context/03-04-SUMMARY.md
  modified:
    - skill/retrieval/models.py
    - skill/retrieval/engine.py
    - skill/retrieval/adapters/policy_official_registry.py
    - skill/retrieval/adapters/policy_official_web_allowlist.py
    - skill/retrieval/adapters/academic_semantic_scholar.py
    - skill/retrieval/adapters/academic_arxiv.py
    - skill/evidence/normalize.py
    - tests/test_retrieval_integration.py
key-decisions:
  - "Extended RetrievalHit with explicit observed-source metadata but kept normalized status markers out of the retrieval layer."
  - "Computed policy version and jurisdiction completeness in build_raw_record from observed hit values only."
  - "Added runtime integration coverage that exercises normalize_hit_candidates and collapse_evidence_records without monkeypatches."
patterns-established:
  - "Observed metadata first: policy and academic adapters now supply only source-observed fields needed by canonicalizers."
  - "Normalization owns completeness markers: build_raw_record preserves raw provenance and derives policy status flags from field presence."
requirements-completed: [EVID-01, EVID-02, EVID-03]
duration: 12 min
completed: 2026-04-12
---

# Phase 03 Plan 04: Runtime Metadata Ingress Summary

**Observed policy and academic retrieval metadata now reaches raw evidence normalization, with runtime regressions proving policy canonicals survive and published/preprint academic variants merge.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-12T15:02:45+08:00
- **Completed:** 2026-04-12T15:14:31+08:00
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Extended `RetrievalHit` and retrieval mapping normalization to carry observed authority, date, version, jurisdiction, DOI, arXiv, author, year, and evidence-level fields.
- Enriched the deterministic policy and academic adapters so live retrieval hits now contain the metadata Phase 3 canonicalizers require.
- Updated `build_raw_record(...)` to preserve raw hit provenance, map observed metadata directly, and derive only policy completeness markers from observed values.
- Added real-path runtime tests proving live policy hits survive canonicalization and live academic published/preprint variants collapse into one canonical citation set.

## Task Commits

Each task was committed atomically through its TDD cycle:

1. **Task 1: Extend live retrieval hits and adapters with explicit observed policy and academic metadata**
   `59a6092` `test(03-04): add failing retrieval metadata regressions`
   `94596dd` `feat(03-04): enrich retrieval hits with observed metadata`
2. **Task 2: Map live RetrievalHit metadata into RawEvidenceRecord and prove real policy and academic canonicalization paths**
   `e25397c` `test(03-04): add failing runtime evidence normalization tests`
   `552b621` `feat(03-04): map live retrieval metadata into raw evidence`

## Files Created/Modified

- `skill/retrieval/models.py` - expanded the shared hit contract with observed policy and academic metadata fields
- `skill/retrieval/engine.py` - preserved optional observed metadata when adapters return mapping-shaped hit payloads
- `skill/retrieval/adapters/policy_official_registry.py` - added authority and date-bearing official policy fixtures
- `skill/retrieval/adapters/policy_official_web_allowlist.py` - added allowlisted policy fixtures with observed authority/date/version metadata
- `skill/retrieval/adapters/academic_semantic_scholar.py` - added DOI, author, year, and evidence-level metadata to scholarly fixtures
- `skill/retrieval/adapters/academic_arxiv.py` - added arXiv, author, year, and evidence-level metadata to preprint fixtures
- `skill/evidence/normalize.py` - mapped observed RetrievalHit metadata into RawEvidenceRecord and derived policy completeness flags from field presence
- `tests/test_retrieval_integration.py` - added RED coverage for retrieval metadata emission and mapping normalization
- `tests/test_evidence_runtime_integration.py` - added real normalize-plus-collapse regressions for live policy and academic inputs

## Decisions Made

- Kept retrieval-layer metadata limited to observed source values and deferred `version_status`, `jurisdiction_status`, and canonical match confidence to normalization.
- Used title plus first-author plus year alignment between Semantic Scholar and arXiv fixtures so the real academic canonicalizer exercises the intended published/preprint merge path.
- Verified the normalization fix against the broader evidence suite, not just the new runtime tests, because `build_raw_record(...)` is a shared ingress point.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Runtime metadata ingress is now populated for policy and academic evidence, so downstream canonicalization and packing stages receive the fields they were designed for.
- `skill/retrieval/orchestrate.py` still returns prioritized raw hits outward; the remaining Phase 3 work should wire the bounded canonical evidence pack into the downstream response or synthesis boundary.

## Self-Check: PASSED

- Found summary artifact at `.planning/phases/03-evidence-normalization-budgeted-context/03-04-SUMMARY.md`
- Found task commits `59a6092`, `94596dd`, `e25397c`, and `552b621` in git history
