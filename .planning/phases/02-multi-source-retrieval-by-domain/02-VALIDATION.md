---
phase: 2
slug: multi-source-retrieval-by-domain
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-11
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Bootstrap command** | `python -m pip install -e .[dev]` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_route_contracts.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After Wave 0 / bootstrap task:** Run `python -m pip install -e .[dev]`
- **After every remaining task commit:** Run the task's exact `<automated>` command
- **After retrieval-engine wave:** Run `pytest tests/test_retrieval_concurrency.py -q && pytest tests/test_retrieval_fallback.py -q`
- **After priority/ranking wave:** Run `pytest tests/test_domain_priority.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | RETR-01 | T-02-01 / T-02-02 | Retrieval plan and runtime controller enforce per-source timeout and overall deadline without browser fallback | unit/integration | `python -c "from skill.api.schema import RouteResponse; from skill.orchestrator.intent import classify_query; from skill.orchestrator.planner import plan_route; route=plan_route(classify_query('自动驾驶政策对行业影响')); assert route.route_label=='mixed'; assert route.primary_route in {'policy','industry','academic'}; print('phase2-bootstrap-ok')"` | ✅ planned | ⬜ pending |
| 02-01-02 | 01 | 1 | RETR-01, RETR-02 | T-02-01 / T-02-03 | Async fan-out cancels slow sources at deadline and maps timeout / rate-limit / empty-hit into deterministic failure categories | integration | `pytest tests/test_retrieval_concurrency.py -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | RETR-02 | T-02-03 / T-02-04 | Fallback FSM treats `no_hits`, `timeout`, `rate_limited`, and adapter errors deterministically and returns structured failure/gaps outcomes | integration | `pytest tests/test_retrieval_fallback.py -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | RETR-03, RETR-04, RETR-05 | T-02-05 / T-02-06 | Domain priority applies hard authority tiers before recency/relevance and prevents generic web from outranking official or scholarly sources | unit/integration | `pytest tests/test_domain_priority.py -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | RETR-01, RETR-02, RETR-05 | T-02-02 / T-02-04 | API-level retrieval contract exposes usable results or structured gaps without losing mixed-route dominance and credibility-tier ordering | integration | `pytest -q` | ✅ existing suite + W0 additions | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Readiness Requirements

- [ ] `tests/test_retrieval_concurrency.py` exists for RETR-01
- [ ] `tests/test_retrieval_fallback.py` exists for RETR-02
- [ ] `tests/test_domain_priority.py` exists for RETR-03 / RETR-04 / RETR-05
- [ ] Retrieval fixture set covers `429`, timeout, empty hits, and mixed-route supplemental-source scenarios
- [ ] `python -m pip install -e .[dev]` remains the single bootstrap step before running retrieval tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Concurrency cap tuning on 4 vCPU budget | RETR-01 | Final semaphore and overall deadline values are environment-sensitive and should be spot-checked under contest-like hardware | Run the planned benchmark sweep for cap values (for example 4/6/8) and confirm deadline convergence remains stable before locking defaults |

---

## Validation Sign-Off

- [x] All planned task groups have automated verification commands or explicit Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing retrieval test files
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
