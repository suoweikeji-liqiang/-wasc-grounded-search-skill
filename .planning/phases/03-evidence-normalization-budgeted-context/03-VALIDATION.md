---
phase: 03
slug: evidence-normalization-budgeted-context
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-12
---

# Phase 03 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none - use environment guard for plugin isolation |
| **Quick run command** | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py tests/test_evidence_pack.py -q` |
| **Full suite command** | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's exact `<automated>` command with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- **After every plan wave:** Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | EVID-01 | T-03-01 | Wave 0 fixtures and evidence regressions lock raw/canonical separation, retained-slice limits, and canonicalization edge cases | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py tests/test_evidence_policy.py tests/test_evidence_academic.py -q` | No W0 | pending |
| 03-01-02 | 01 | 1 | EVID-01 | T-03-02 | Raw retrieval hits normalize into canonical evidence candidates without losing provenance or silently inventing policy metadata | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py tests/test_evidence_policy.py tests/test_evidence_academic.py -q` | No W0 | pending |
| 03-02-01 | 02 | 2 | EVID-02,EVID-03 | T-03-04 | Policy and academic canonicalization enforce explicit completeness markers, published-first preference, linked variants, and heuristic confidence | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_policy.py tests/test_evidence_academic.py -q` | No W0 | pending |
| 03-02-02 | 02 | 2 | EVID-01 | T-03-06 | Domain-aware duplicate collapse merges complementary metadata deterministically while keeping conservative industry dedupe behavior | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_dedupe.py tests/test_evidence_policy.py tests/test_evidence_academic.py -q` | No W0 | pending |
| 03-03-01 | 03 | 3 | EVID-04 | T-03-07 / T-03-08 | Evidence scoring and pack builder enforce hard token budget, top-K ceiling, slice-first pruning, and mixed supplemental reserve | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_pack.py -q` | No W0 | pending |
| 03-03-02 | 03 | 3 | EVID-01,EVID-04 | T-03-09 | Retrieval integration runs the post-priority evidence pipeline additively and exposes only safe clip-state metadata | integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_pack.py tests/test_retrieval_integration.py -q` | Yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_evidence_models.py` - canonical evidence contract and raw/canonical separation
- [ ] `tests/test_evidence_policy.py` - policy metadata completeness and explicit missing/inferred markers
- [ ] `tests/test_evidence_academic.py` - DOI/arXiv/heuristic canonicalization and linked variants
- [ ] `tests/test_evidence_dedupe.py` - deterministic duplicate collapse and metadata merge behavior
- [ ] `tests/test_evidence_pack.py` - hard budget + top-K + mixed supplemental reserve

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Initial token-budget defaults are sensible for later MiniMax synthesis | EVID-04 | Real synthesis token behavior is not yet available in Phase 3 | Inspect packed evidence stats on representative policy, academic, and mixed fixtures; confirm clipping occurs only on over-budget cases and supplemental evidence is still present for mixed queries |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
