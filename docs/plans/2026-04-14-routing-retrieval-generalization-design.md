# Routing And Retrieval Generalization Design

**Goal:** Improve hidden-set robustness without overfitting to the generated 50-case benchmark.

**Problem:** The current system over-routes real English queries into `mixed`, and live policy/industry retrieval depends too heavily on slow page fetches inside tight per-source budgets. That combination causes timeout-heavy failure on realistic public-source questions.

**Principles**

- Fix generic decision rules, not individual benchmark questions.
- Prefer structured official/public signals that already exist in search results.
- Keep headless-only behavior.
- Preserve current shortcut path for easy wins, but make the live path degrade gracefully instead of timing out.

**Planned Changes**

- Routing:
  - expand generic English domain hints for policy, academic, and industry queries
  - stop treating every non-zero low-signal query as `mixed`
  - keep `mixed` reserved for explicit cross-domain intent or real two-domain ambiguity
- Policy retrieval:
  - expand official allowlist and domain routing for EU, UK, and US official sources
  - allow strong official-domain candidates to survive even when page metadata extraction is incomplete
  - continue using page fetch for enrichment, but not as a hard admission gate
- Industry retrieval:
  - treat SEC EDGAR structured hits as first-class evidence without mandatory page fetch
  - use candidate snippet fallback more aggressively for public web results

**Verification**

- Add failing tests first for:
  - hidden-like English routing regressions
  - official policy candidates with empty page fetch
  - SEC filing queries that should not require second fetches
- Re-run targeted suites, then the generated 50-case benchmark to measure generalized improvement.
