---
phase: 04-grounded-structured-answer-generation
plan: 02
subsystem: synthesis
tags: [prompt, generator, citation-check, uncertainty, minimax]
requires:
  - phase: 04-01
    provides: grounded answer contracts and answer-state taxonomy
provides:
  - canonical-evidence prompt serialization
  - MiniMax-compatible structured-generation boundary
  - fail-closed citation validation
  - deterministic uncertainty-note derivation
affects: [phase-04-orchestration, answer-api, verifier]
tech-stack:
  added: []
  patterns: [json-only generation prompt, fail-closed citation gate, deterministic uncertainty prefixes]
key-files:
  created: [skill/synthesis/prompt.py, skill/synthesis/generator.py, skill/synthesis/citation_check.py, skill/synthesis/uncertainty.py, tests/test_answer_generator.py, tests/test_answer_citation_check.py]
  modified: []
key-decisions:
  - "Kept the live MiniMax client as a thin injectable boundary so all phase tests remain offline and deterministic."
  - "Made citation validation compare quote_text against retained slice text instead of trusting links alone."
patterns-established:
  - "Prompt payloads serialize evidence_id, source_record_id, and retained slice text explicitly."
  - "Uncertainty notes come from observable evidence conditions with fixed prefixes."
requirements-completed: [OUTP-01, OUTP-02, OUTP-03]
duration: 14 min
completed: 2026-04-12
---

# Phase 04 Plan 02: Synthesis Core Summary

**Bounded evidence now flows through a strict prompt, structured draft parser, citation checker, and deterministic uncertainty-note builder**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-12T08:29:00+08:00
- **Completed:** 2026-04-12T08:43:00+08:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added prompt serialization that emits canonical evidence IDs and retained-slice identifiers for grounded synthesis.
- Added an injectable MiniMax-compatible generation boundary with strict JSON parsing into answer drafts.
- Added fail-closed citation validation and deterministic uncertainty-note assembly.

## Task Commits

Implementation landed in one TDD-shaped commit because generator parsing and citation validation needed to go green together against the new tests:

1. **Task 1 + Task 2: prompt builder, generator, citation checker, and uncertainty notes** - `cec4856` (`feat`)

## Files Created/Modified
- `skill/synthesis/prompt.py` - JSON-only grounded-answer prompt builder
- `skill/synthesis/generator.py` - model-client protocol, MiniMax client stub, and strict draft parser
- `skill/synthesis/citation_check.py` - fail-closed citation validation against retained slices
- `skill/synthesis/uncertainty.py` - deterministic uncertainty-note derivation
- `tests/test_answer_generator.py` - prompt and strict-parse regressions
- `tests/test_answer_citation_check.py` - citation-failure and uncertainty-prefix regressions

## Decisions Made
- Kept the default MiniMax client offline-safe for this phase so tests do not require credentials or network calls.
- Treated quote mismatch as a grounding failure even when the evidence ID exists, because OUTP-02 requires traceability to actual evidence text.

## Deviations from Plan

### Auto-fixed Execution Adjustment

**1. Combined the two plan tasks into one green commit**
- **Found during:** Wave 2 TDD cycle
- **Issue:** The prompt and parser tests in Task 1 and the citation-check tests in Task 2 share the same end-to-end draft shape.
- **Fix:** Executed the red-green cycle across both tasks and committed the coherent passing implementation once.
- **Files modified:** `skill/synthesis/prompt.py`, `skill/synthesis/generator.py`, `skill/synthesis/citation_check.py`, `skill/synthesis/uncertainty.py`, `tests/test_answer_generator.py`, `tests/test_answer_citation_check.py`
- **Verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_generator.py tests/test_answer_citation_check.py -q`
- **Committed in:** `cec4856`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** No scope change. The combined commit kept the intended TDD proof while avoiding a half-green intermediate state.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The answer orchestrator can now reuse real prompt, parsing, citation, and uncertainty modules.
- No blockers found for Plan 03.

## Self-Check: PASSED

- Verified `tests/test_answer_generator.py` and `tests/test_answer_citation_check.py` pass.
- Verified commit `cec4856` exists in git history.
