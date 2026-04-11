---
phase: 02-multi-source-retrieval-by-domain
reviewed: 2026-04-11T17:32:01Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - skill/retrieval/fallback_fsm.py
  - skill/retrieval/engine.py
  - skill/orchestrator/retrieval_plan.py
  - tests/test_retrieval_fallback.py
  - .planning/phases/02-multi-source-retrieval-by-domain/02-VERIFICATION.md
  - .planning/phases/02-multi-source-retrieval-by-domain/02-04-SUMMARY.md
  - skill/api/schema.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 02: Code Review Report (Re-review After 02-04)

**Reviewed:** 2026-04-11T17:32:01Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Re-reviewed the phase-02 gap-closure changes in fallback FSM/runtime planner + tests, and validated adjacent verification artifacts.

Resolved from prior review:
- WR-01 (plan fallback scope ignored in runtime): **resolved** in `skill/retrieval/engine.py` via `allowed_fallback_transitions` derived from `plan.fallback_sources`.
- WR-03 (429 mapping missed `response.status_code`): **resolved** in `skill/retrieval/fallback_fsm.py` and covered by new regression test.

Still open from prior review:
- WR-02 (cancellation swallowed): **remains**.
- IN-01 (response envelope invariants weaker than outcome invariants): **remains**.

Verification executed:
- `pytest tests/test_retrieval_concurrency.py tests/test_retrieval_fallback.py tests/test_domain_priority.py tests/test_retrieval_integration.py -q`
- Result: `33 passed`

Targeted probe executed:
- `_run_single_source(...)` with adapter raising `asyncio.CancelledError` currently returns `failure_gaps/adapter_error`, confirming cancellation is still consumed.

## Warnings

### WR-01: Cancellation Is Still Swallowed As Adapter Failure

**File:** `D:\study\WASC\skill\retrieval\engine.py:89-99`
**Issue:** `_run_single_source(...)` catches `BaseException` and converts `asyncio.CancelledError` into `failure_gaps` with `adapter_error`. This breaks cooperative cancellation semantics and can misreport cancellations as adapter faults.
**Fix:**
```python
try:
    if semaphore is not None:
        async with semaphore:
            raw_hits = await _invoke_adapter()
    else:
        raw_hits = await _invoke_adapter()
except asyncio.CancelledError:
    raise
except Exception as exc:
    return SourceExecutionResult(
        source_id=source_id,
        status="failure_gaps",
        failure_reason=map_exception_to_failure_reason(exc),
        gaps=(source_id,),
    )
```

## Info

### IN-01: RetrieveResponse Still Lacks Status-Dependent Invariant Validation

**File:** `D:\study\WASC\skill\api\schema.py:101`
**Issue:** `RetrieveOutcome` enforces cross-field invariants, but `RetrieveResponse` still does not enforce equivalent rules (`status='success'` can still carry `failure_reason`, etc.).
**Fix:** Add validators on `RetrieveResponse` mirroring `RetrieveOutcome` status/failure_reason/gaps constraints (or share a validated base model).

---

_Reviewed: 2026-04-11T17:32:01Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

COMPLETION_MARKER: PHASE_02_RE_REVIEW_COMPLETE
