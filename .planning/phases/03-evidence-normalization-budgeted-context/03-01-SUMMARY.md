---
phase: 03-evidence-normalization-budgeted-context
plan: 01
subsystem: evidence
tags: [python, pytest, dataclasses, evidence-normalization]
requires:
  - phase: 02-multi-source-retrieval-by-domain
    provides: domain-prioritized RetrievalHit outputs and orchestrated retrieval ingress
provides:
  - deterministic phase 3 fixtures for policy, academic, and mixed-route evidence cases
  - frozen raw and canonical evidence dataclasses with explicit metadata status fields
  - normalization ingress helpers that preserve retrieval provenance without fabricating policy metadata
affects: [03-02, 03-03, phase-04-answer-synthesis]
tech-stack:
  added: []
  patterns: [frozen dataclass evidence contracts, explicit metadata status markers, raw-to-canonical normalization boundary]
key-files:
  created:
    - skill/evidence/models.py
    - skill/evidence/normalize.py
    - tests/test_evidence_models.py
    - tests/test_evidence_policy.py
    - tests/test_evidence_academic.py
    - tests/fixtures/evidence_phase3_cases.json
  modified: []
key-decisions:
  - "Policy canonical records require explicit jurisdiction_status and version_status instead of silent default values."
  - "Academic linked variants are preserved under canonical records and require an explicit canonical_match_confidence marker."
patterns-established:
  - "Raw and canonical evidence remain side by side through EvidencePack for traceability."
  - "Policy metadata completeness is modeled with separate value fields and explicit status fields."
requirements-completed: [EVID-01, EVID-02, EVID-03]
duration: 2 min
completed: 2026-04-12
---

# Phase 03 Plan 01: Evidence Contracts Summary

**Phase 3 now has deterministic evidence fixtures, frozen raw and canonical evidence contracts, and normalization ingress helpers that preserve retrieval provenance.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T09:28:26+08:00
- **Completed:** 2026-04-12T09:30:43+08:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added deterministic Phase 3 fixture coverage for policy duplicates, academic variant pairs, and mixed-route candidates.
- Added frozen evidence contracts for raw records, retained slices, linked variants, canonical evidence, and evidence packs.
- Added normalization helpers that keep raw retrieval hit provenance and initialize explicit non-fabricated policy metadata state.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create deterministic Phase 3 fixtures and evidence contract regressions** - `11d3688` (test)
2. **Task 2: Add raw-to-canonical evidence contracts and normalization ingress helpers** - `c62af99` (feat)

**Plan metadata:** committed separately as the summary-only docs commit for this plan

## Files Created/Modified
- `skill/evidence/models.py` - Frozen dataclasses and validation for raw evidence, slices, linked variants, canonical evidence, and packs.
- `skill/evidence/normalize.py` - Retrieval-hit ingress helpers for raw evidence construction and route-role normalization.
- `tests/test_evidence_models.py` - Contract regressions for provenance retention, immutability, slice limits, and linked variants.
- `tests/test_evidence_policy.py` - Policy regressions for minimum entry rules and explicit `version_status` / `jurisdiction_status` behavior.
- `tests/test_evidence_academic.py` - Academic regressions for published-first canonical records, linked variants, and heuristic match markers.
- `tests/fixtures/evidence_phase3_cases.json` - Deterministic Phase 3 fixtures covering policy, academic, and mixed-route evidence cases.

## Decisions Made

- Kept policy incompleteness explicit by separating concrete metadata values from their status markers.
- Limited canonical retained slices to two by default in the contract layer so later packing work starts from a bounded document shape.
- Required explicit canonical match confidence for academic linked variants so heuristic merges cannot masquerade as strong identifier matches.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- PowerShell treated the `rg` glob in Task 1's acceptance check literally, so the verification was rerun with explicit file paths.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `03-02` can build domain-specific canonicalization logic on top of stable evidence contracts and fixtures.
- `03-03` can implement budgeted evidence packing against the retained-slice and route-role contracts added here.

## Self-Check: PASSED

- Verified `.planning/phases/03-evidence-normalization-budgeted-context/03-01-SUMMARY.md` exists on disk.
- Verified task commit `11d3688` exists in git history.
- Verified task commit `c62af99` exists in git history.

---
*Phase: 03-evidence-normalization-budgeted-context*
*Completed: 2026-04-12*
