---
phase: 04
slug: grounded-structured-answer-generation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-12
---

# Phase 04 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none - use environment guard for plugin isolation |
| **Quick run command** | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py tests/test_answer_citation_check.py -q` |
| **Full suite command** | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's exact `<automated>` command with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- **After every plan wave:** Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | OUTP-01,OUTP-02,OUTP-03 | T-04-01 / T-04-02 | Wave 0 fixtures and answer-contract regressions lock required fields, explicit answer states, and evidence-bound citation identifiers | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py -q` | No W0 | pending |
| 04-01-02 | 01 | 1 | OUTP-01,OUTP-02,OUTP-03 | T-04-03 / T-04-04 | Internal synthesis models and answer-state helpers reject ambiguous success cases and extra schema fields | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py -q` | No W0 | pending |
| 04-02-01 | 02 | 2 | OUTP-01,OUTP-02 | T-04-05 | Prompt builder and generator produce strict structured JSON with per-key-point citations using fake model clients | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_generator.py -q` | No W0 | pending |
| 04-02-02 | 02 | 2 | OUTP-02,OUTP-03 | T-04-06 / T-04-07 | Citation checker fails closed on dangling citations and uncertainty notes surface clipping, gaps, and heuristic evidence markers deterministically | unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_generator.py tests/test_answer_citation_check.py -q` | No W0 | pending |
| 04-03-01 | 03 | 3 | OUTP-01,OUTP-03 | T-04-08 | End-to-end answer orchestration reuses browser-free retrieval, maps answer state explicitly, and never leaks internal telemetry | integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_integration.py -q` | No W0 | pending |
| 04-03-02 | 03 | 3 | OUTP-01,OUTP-02,OUTP-03 | T-04-09 / T-04-10 | `/answer` endpoint returns grounded, insufficient, and retrieval-failure payloads with conclusion, key points, sources, and uncertainty | integration | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q` | No W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/answer_phase4_cases.json` - grounded, insufficient, and retrieval-failure answer fixtures
- [ ] `tests/test_answer_contracts.py` - answer contract and required-field regressions
- [ ] `tests/test_answer_state_mapping.py` - retrieval-to-answer state rules
- [ ] `tests/test_answer_generator.py` - prompt/JSON parse behavior with fake model client
- [ ] `tests/test_answer_citation_check.py` - citation-binding and fail-closed validation
- [ ] `tests/test_answer_integration.py` - retrieve -> synthesize -> validate orchestration path
- [ ] `tests/test_api_answer_endpoint.py` - `/answer` endpoint response states and schema

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live MiniMax request and parse behavior remain faithful to the strict JSON contract once credentials are available | OUTP-01, OUTP-02 | Networked model behavior cannot be proven in offline unit tests alone | Run one policy and one academic query against the real model client, inspect the raw JSON text, and confirm every returned key point cites an existing evidence ID plus source record ID |
| Insufficient-evidence conclusion language stays honest and non-overclaiming on representative benchmark queries | OUTP-03 | Final wording quality depends on model output and requires human judgment | Review at least one grounded-success, one insufficient-evidence, and one retrieval-failure response and confirm the conclusion text matches the answer state |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
