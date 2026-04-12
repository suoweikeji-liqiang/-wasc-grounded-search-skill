---
phase: 03
slug: evidence-normalization-budgeted-context
status: draft
nyquist_compliant: false
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

- **After every task commit:** Run the smallest relevant Phase 3 test file(s) with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- **After every plan wave:** Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | EVID-01 | T-03-01 | Raw retrieval hits normalize into canonical evidence without losing provenance | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_models.py -q` | No W0 | pending |
| 03-01-02 | 01 | 1 | EVID-02 | T-03-02 | Policy metadata absence is explicit; authority + date minimum enforced | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_policy.py -q` | No W0 | pending |
| 03-02-01 | 02 | 1 | EVID-03 | T-03-03 | Academic canonicalization preserves linked variants and merge confidence | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_academic.py -q` | No W0 | pending |
| 03-02-02 | 02 | 1 | EVID-01 | T-03-04 | Duplicate collapse merges complementary metadata deterministically | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_dedupe.py -q` | No W0 | pending |
| 03-03-01 | 03 | 2 | EVID-04 | T-03-05 | Budget pack enforces hard token cap, top-K ceiling, and mixed supplemental reserve | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_evidence_pack.py -q` | No W0 | pending |
| 03-03-02 | 03 | 2 | EVID-01,EVID-04 | T-03-06 | Retrieval-to-pack integration remains deterministic under current route rules | integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_retrieval_integration.py -q` | Yes | pending |

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
