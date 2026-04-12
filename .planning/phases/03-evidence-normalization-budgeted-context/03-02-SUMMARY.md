---
phase: 03-evidence-normalization-budgeted-context
plan: 02
subsystem: evidence
tags: [python, pytest, evidence-normalization, dedupe, canonicalization]
requires:
  - phase: 03-evidence-normalization-budgeted-context
    provides: Phase 3 evidence contracts, fixtures, and normalization ingress helpers from 03-01
provides:
  - policy-specific canonicalization with explicit metadata completeness handling
  - academic canonicalization with published-first selection and linked variants
  - deterministic cross-domain duplicate collapse with conservative industry merging
affects: [03-03, phase-04-answer-synthesis]
tech-stack:
  added: []
  patterns: [domain-specific canonicalizers behind shared collapse orchestration, conservative same-domain industry dedupe]
key-files:
  created:
    - skill/evidence/policy.py
    - skill/evidence/academic.py
    - skill/evidence/dedupe.py
  modified:
    - tests/test_evidence_policy.py
    - tests/test_evidence_academic.py
    - tests/test_evidence_dedupe.py
key-decisions:
  - "Policy duplicates merge on authority plus normalized title plus shared version/date signals, while invalid records missing authority or all dates are dropped."
  - "Academic grouping merges DOI and arXiv aliases into one canonical cluster and marks title-author-year fallbacks as heuristic."
  - "Industry records merge only under same-domain high title and snippet similarity, with complementary metadata folded into the canonical record."
patterns-established:
  - "Per-domain canonicalizers feed a single deterministic collapse function that sorts canonicals by evidence_id."
  - "Canonical records keep first-seen raw provenance order even when the final output is sorted for determinism."
requirements-completed: [EVID-01, EVID-02, EVID-03]
duration: 6 min
completed: 2026-04-12
---

# Phase 03 Plan 02: Evidence Canonicalization Summary

**Policy, academic, and industry evidence now collapse into deterministic canonical records with explicit metadata status handling and preserved raw provenance.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-12T09:36:08+08:00
- **Completed:** 2026-04-12T09:42:10+08:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added policy canonicalization that groups version/date-aware duplicates, rejects incomplete records, and keeps publication/effective dates separate.
- Added academic canonicalization that prefers published variants, retains linked variants, and labels heuristic title-author-year merges.
- Added cross-domain duplicate collapse that routes policy and academic records to their canonicalizers and merges same-domain industry duplicates conservatively while preserving raw provenance.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement policy metadata normalization and academic canonicalization modules**
   - `7e1938d` (test) - failing regressions for policy and academic canonicalization behavior
   - `fe0e800` (feat) - policy and academic canonicalization modules
2. **Task 2: Implement deterministic duplicate collapse and metadata merge orchestration**
   - `14b0d99` (test) - failing regressions for domain routing, metadata merge, and over-merge rejection
   - `fa6d348` (feat) - duplicate collapse orchestration with conservative industry merging

**Plan metadata:** committed separately as a summary-only docs commit

## Files Created/Modified
- `skill/evidence/policy.py` - Policy canonicalization and explicit metadata carry-forward helpers.
- `skill/evidence/academic.py` - Academic canonical key alias grouping, published-first selection, and linked variant assembly.
- `skill/evidence/dedupe.py` - Domain routing, deterministic canonical sorting, and conservative industry merge orchestration.
- `tests/test_evidence_policy.py` - Regression coverage for policy duplicate grouping and minimum-entry rejection.
- `tests/test_evidence_academic.py` - Regression coverage for published-first and heuristic academic merges.
- `tests/test_evidence_dedupe.py` - Regression coverage for same-domain industry dedupe, raw provenance retention, and over-merge rejection.

## Decisions Made

- Merged academic records by alias-connected identifiers so a published DOI record and matching arXiv preprint collapse into one canonical cluster.
- Kept industry dedupe intentionally narrow by requiring the same host plus high title and snippet similarity instead of event-level similarity.
- Preserved first-seen raw record order inside each canonical record while sorting final canonical outputs by `evidence_id` for deterministic downstream behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Academic grouping initially treated DOI and arXiv identifiers as separate clusters; this was corrected during the GREEN phase by merging alias-connected identifiers into one group before canonical selection.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `03-03` can build scoring and budgeted packing on top of stable canonical evidence outputs.
- Phase 4 answer synthesis can consume canonical records with explicit status fields, linked variants, and retained raw provenance.

## Self-Check: PASSED

- Verified `.planning/phases/03-evidence-normalization-budgeted-context/03-02-SUMMARY.md` exists on disk.
- Verified task commit `7e1938d` exists in git history.
- Verified task commit `fe0e800` exists in git history.
- Verified task commit `14b0d99` exists in git history.
- Verified task commit `fa6d348` exists in git history.

---
*Phase: 03-evidence-normalization-budgeted-context*
*Completed: 2026-04-12*
