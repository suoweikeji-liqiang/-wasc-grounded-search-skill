# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 - Initial MVP

**Shipped:** 2026-04-13
**Phases:** 5 | **Plans:** 17 | **Sessions:** not tracked

### What Was Built

- Browser-free route classification and source-family planning for policy, industry, academic, and mixed queries.
- Concurrent domain-aware retrieval with canonical evidence normalization and bounded synthesis context.
- Grounded `/answer` generation with explicit outcome states, citation gating, and live benchmark-ready runtime budgets.
- A locked `10 x 5` benchmark harness plus grouped repeatability evaluation and report artifacts.

### What Worked

- Breaking the competition goal into routing, retrieval, evidence, answer, and reliability phases kept each layer independently verifiable.
- Offline deterministic tests around public contracts made rapid iteration possible without provider or browser dependencies.
- Keeping canonical evidence as the shared boundary between retrieval and answer generation reduced cross-phase drift.

### What Was Inefficient

- Live benchmark tuning surfaced late, so Phase 5 needed closure work beyond the original offline proof points.
- Human UAT for conclusion honesty stayed open too long and blocked a clean archive until the very end.
- Nyquist discovery stayed partial across Phases 2-5, so milestone cleanup did not end in a fully clean audit.

### Patterns Established

- Lock contracts first, then add runtime behavior behind them.
- Keep browser-free execution as a hard architectural constraint.
- Treat benchmark harnesses as product surfaces, not just test utilities.

### Key Lessons

1. Human semantic checks should be scheduled as explicit UAT tasks before the final archive pass.
2. Live-model benchmark behavior needs earlier regression hooks, even when the main development loop is deterministic and offline.
3. Advisory debt should stay visible in archive documents instead of being silently normalized away.

### Cost Observations

- Model mix: not tracked
- Sessions: not tracked
- Notable: offline deterministic verification kept most iteration cheap; live-model work was reserved for final benchmark closure.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not tracked | 5 | Established a phase-driven, contract-first competition workflow |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|--------------------|
| v1.0 | 172 passing | not tracked | Browser-free core plus deterministic benchmark harness |

### Top Lessons To Recheck Next Milestone

1. Contract-first phase boundaries keep multi-stage search pipelines easier to verify and extend.
2. Deterministic offline harnesses should exist before live-model tuning begins.
