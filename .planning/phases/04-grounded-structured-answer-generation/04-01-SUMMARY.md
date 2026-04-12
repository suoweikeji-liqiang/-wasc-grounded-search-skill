---
phase: 04-grounded-structured-answer-generation
plan: 01
subsystem: api
tags: [answer, schema, pydantic, synthesis, state]
requires:
  - phase: 03-05
    provides: canonical evidence as the retrieval response boundary
provides:
  - grounded answer request and response contracts
  - explicit answer-state taxonomy
  - deterministic retrieval-to-answer state mapping
  - wave-0 fixtures for grounded, insufficient, and retrieval-failure outcomes
affects: [phase-04-synthesis, answer-api, verifier]
tech-stack:
  added: []
  patterns: [explicit answer-state taxonomy, evidence-bound citation identifiers, strict answer schema]
key-files:
  created: [skill/synthesis/models.py, skill/synthesis/state.py, tests/fixtures/answer_phase4_cases.json, tests/test_answer_contracts.py, tests/test_answer_state_mapping.py]
  modified: [skill/api/schema.py]
key-decisions:
  - "Separated final answer state from retrieval status so grounded success is decided only after grounding checks."
  - "Made claim citations require evidence_id plus source_record_id instead of allowing link-only references."
patterns-established:
  - "Final answer contracts always include conclusion, key_points, sources, uncertainty_notes, and gaps."
  - "Grounded success requires all surfaced key points to be citation-backed."
requirements-completed: [OUTP-01, OUTP-02, OUTP-03]
duration: 12 min
completed: 2026-04-12
---

# Phase 04 Plan 01: Answer Contract Summary

**Grounded answer contracts, evidence-bound citations, and explicit answer-state mapping now exist as the Phase 4 synthesis foundation**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-12T08:16:00+08:00
- **Completed:** 2026-04-12T08:28:00+08:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added deterministic fixture coverage for grounded success, insufficient evidence, and retrieval failure answer states.
- Introduced internal synthesis contracts for citations, key points, sources, and answer drafts.
- Extended the public API schema with strict `AnswerRequest` and `AnswerResponse` models.

## Task Commits

Implementation landed in one TDD-shaped commit because the Wave 0 tests and the minimal contract code had to turn green together:

1. **Task 1 + Task 2: answer fixtures, synthesis contracts, and answer-state helper** - `abbca15` (`feat`)

## Files Created/Modified
- `skill/synthesis/models.py` - internal answer, citation, key-point, and source contracts
- `skill/synthesis/state.py` - retrieval-to-answer status mapping
- `skill/api/schema.py` - public answer request and response schema
- `tests/fixtures/answer_phase4_cases.json` - grounded, insufficient, and retrieval-failure fixtures
- `tests/test_answer_contracts.py` - contract and strict-schema regressions
- `tests/test_answer_state_mapping.py` - deterministic answer-state regressions

## Decisions Made
- Final answer state is not a mirror of retrieval status; it is computed from retrieval outcome plus grounded-claim completeness.
- Claim citations must name both the evidence object and the retained slice identifier to keep Phase 4 traceable.

## Deviations from Plan

### Auto-fixed Execution Adjustment

**1. Combined the two plan tasks into one green commit**
- **Found during:** Wave 1 TDD cycle
- **Issue:** The Wave 0 tests in Task 1 could not pass without the contracts and state helper from Task 2.
- **Fix:** Executed the red-green cycle across both tasks, then committed the coherent green state once.
- **Files modified:** `skill/synthesis/models.py`, `skill/synthesis/state.py`, `skill/api/schema.py`, `tests/fixtures/answer_phase4_cases.json`, `tests/test_answer_contracts.py`, `tests/test_answer_state_mapping.py`
- **Verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py -q`
- **Committed in:** `abbca15`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** No scope change. The combined commit preserved the intended TDD boundary and shipped the exact planned artifacts.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Prompt construction and citation checking can now target stable answer contracts.
- No blockers found for Plan 02.

## Self-Check: PASSED

- Verified `tests/test_answer_contracts.py` and `tests/test_answer_state_mapping.py` pass.
- Verified commit `abbca15` exists in git history.
