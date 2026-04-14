# Live Retrieval Adapters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the default fixture-backed retrieval adapters with live network-backed adapters while preserving the current high-precision routing, evidence, and grounded-answer architecture.

**Architecture:** Keep the existing retrieval planner and evidence pipeline untouched. Add shared live retrieval support under `skill/retrieval/live/`, then refit the policy, academic, and industry adapters to call those shared clients and emit normalized `RetrievalHit` objects. Fixture mode remains available for deterministic tests and offline fallback.

**Tech Stack:** Python, FastAPI, `httpx`, optional headless Playwright, BeautifulSoup/lxml-style HTML parsing, existing evidence/retrieval modules, pytest

---

### Task 1: Add Failing Tests For Live Adapter Mode Selection

**Files:**
- Modify: `tests/test_api_answer_endpoint.py`
- Modify: `tests/test_retrieval_integration.py`
- Modify: `tests/test_domain_priority.py`

**Step 1: Write the failing test**

Add tests that prove:

- default adapter registry resolves to live implementations when live mode is enabled
- fixture mode remains selectable for deterministic offline tests
- industry adapter contract still preserves credibility-tier semantics after the mode switch

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_api_answer_endpoint.py tests/test_retrieval_integration.py tests/test_domain_priority.py -q
```

Expected:

- FAIL because live-mode selection and adapter switching do not exist yet

**Step 3: Write minimal implementation**

Add configuration plumbing for adapter mode selection only. Do not implement network clients yet.

**Step 4: Run test to verify it passes**

Run the same command and verify the new mode-selection assertions pass.

**Step 5: Commit**

Do not commit yet.

### Task 2: Add Shared Live Retrieval Config And Cache Helpers

**Files:**
- Modify: `pyproject.toml`
- Create: `skill/config/live_retrieval.py`
- Create: `skill/retrieval/live/__init__.py`
- Create: `skill/retrieval/live/cache.py`
- Test: `tests/test_retrieval_live_config.py`

**Step 1: Write the failing test**

Add tests for:

- env-driven live/fixture mode parsing
- search engine enablement parsing
- browser headless settings
- bounded cache key and TTL behavior

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_retrieval_live_config.py -q
```

Expected:

- FAIL because the config and cache helpers do not exist

**Step 3: Write minimal implementation**

Implement:

- a small config loader for live retrieval settings
- a bounded in-memory TTL cache helper
- dependency additions needed for the later live clients

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 3: Add Failing Tests For Shared Search Discovery Clients

**Files:**
- Create: `skill/retrieval/live/clients/__init__.py`
- Create: `skill/retrieval/live/clients/http.py`
- Create: `skill/retrieval/live/clients/search_discovery.py`
- Create: `skill/retrieval/live/parsers/serp.py`
- Test: `tests/test_live_search_discovery.py`

**Step 1: Write the failing test**

Add tests that mock network responses and verify:

- DuckDuckGo discovery returns normalized candidate results
- Bing discovery returns normalized candidate results
- Google discovery failures do not break the aggregate search path
- duplicate URLs across engines collapse correctly

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_live_search_discovery.py -q
```

Expected:

- FAIL because shared discovery clients and SERP parsers do not exist

**Step 3: Write minimal implementation**

Implement:

- shared HTTP request wrapper
- simple HTML SERP parsers
- multi-engine discovery aggregation with timeout-safe fallback

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 4: Add Optional Headless Fetch Support

**Files:**
- Create: `skill/retrieval/live/clients/browser_fetch.py`
- Create: `skill/retrieval/live/parsers/page_content.py`
- Test: `tests/test_live_browser_fetch.py`

**Step 1: Write the failing test**

Add tests that verify:

- plain HTTP fetch is attempted first
- browser fetch is only used when enabled and required
- browser configuration is headless-only
- extracted page content is clipped to safe bounds for snippets

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_live_browser_fetch.py -q
```

Expected:

- FAIL because no browser fetch helper exists

**Step 3: Write minimal implementation**

Implement:

- optional headless Playwright fetch wrapper
- plain HTTP first, browser fallback second
- safe content extraction helper

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 5: Replace Academic Fixture Adapters With Live Implementations

**Files:**
- Modify: `skill/retrieval/adapters/academic_semantic_scholar.py`
- Modify: `skill/retrieval/adapters/academic_arxiv.py`
- Create: `skill/retrieval/live/clients/academic_api.py`
- Create: `skill/retrieval/live/parsers/academic.py`
- Test: `tests/test_academic_live_adapters.py`
- Modify: `tests/test_retrieval_integration.py`

**Step 1: Write the failing test**

Add tests that mock upstream responses and verify:

- Semantic Scholar adapter preserves `doi`, `first_author`, `year`, and `evidence_level`
- arXiv adapter preserves `arxiv_id`, `first_author`, `year`, and `evidence_level`
- fixture mode still returns deterministic fixtures when forced

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_academic_live_adapters.py tests/test_retrieval_integration.py -q
```

Expected:

- FAIL because the academic adapters still use fixtures only

**Step 3: Write minimal implementation**

Implement live API-backed academic adapters with fixture fallback behind config.

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 6: Replace Industry Fixture Adapter With Multi-Engine Live Discovery

**Files:**
- Modify: `skill/retrieval/adapters/industry_ddgs.py`
- Create: `skill/retrieval/live/parsers/industry.py`
- Test: `tests/test_industry_live_adapter.py`
- Modify: `tests/test_domain_priority.py`
- Modify: `tests/test_retrieval_integration.py`

**Step 1: Write the failing test**

Add tests that mock discovery and page fetch behavior and verify:

- the adapter aggregates candidates from multiple engines
- deterministic credibility tiers are still assigned by domain
- positive query matches outrank weaker but lower-quality matches
- a strong company official hit is retained when relevant

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_industry_live_adapter.py tests/test_domain_priority.py tests/test_retrieval_integration.py -q
```

Expected:

- FAIL because the live industry aggregation path does not exist

**Step 3: Write minimal implementation**

Implement:

- multi-engine discovery for industry queries
- candidate dedupe
- credibility-tier assignment
- bounded page enrichment for snippets

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 7: Replace Policy Fixture Adapters With Official-Domain Live Retrieval

**Files:**
- Modify: `skill/retrieval/adapters/policy_official_registry.py`
- Modify: `skill/retrieval/adapters/policy_official_web_allowlist.py`
- Create: `skill/retrieval/live/parsers/policy.py`
- Test: `tests/test_policy_live_adapters.py`
- Modify: `tests/test_retrieval_integration.py`

**Step 1: Write the failing test**

Add tests that mock search discovery and page fetch behavior and verify:

- only allowlisted official policy domains survive the main registry path
- extracted policy hits preserve `authority`, `jurisdiction`, `publication_date`, `effective_date`, and `version` where observed
- the fallback adapter broadens discovery but still rejects non-official domains

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_policy_live_adapters.py tests/test_retrieval_integration.py -q
```

Expected:

- FAIL because policy live extraction and allowlist filtering do not exist

**Step 3: Write minimal implementation**

Implement:

- official-domain search discovery
- policy metadata extraction from fetched content
- fallback allowlist behavior

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 8: Wire Live Adapter Registry Into The API Entrypoint

**Files:**
- Modify: `skill/api/entry.py`
- Modify: `skill/config/retrieval.py`
- Test: `tests/test_api_answer_endpoint.py`
- Test: `tests/test_api_runtime_benchmark.py`

**Step 1: Write the failing test**

Add tests that verify:

- live registry is used by default
- fixture mode remains available by environment override
- runtime benchmark tests still receive bounded retrieval behavior

**Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_api_answer_endpoint.py tests/test_api_runtime_benchmark.py -q
```

Expected:

- FAIL because the default registry is still fixture-only

**Step 3: Write minimal implementation**

Switch the registry builder to live adapters by default, keeping an explicit fixture override for tests.

**Step 4: Run test to verify it passes**

Run the same command and verify PASS.

**Step 5: Commit**

Do not commit yet.

### Task 9: Update Setup Docs For Live Retrieval Operation

**Files:**
- Modify: `README.md`
- Modify: `SETUP.md`
- Test: manual review only

**Step 1: Write the documentation changes**

Document:

- required environment variables
- browser installation requirements
- live vs fixture mode
- optional live integration test commands

**Step 2: Verify the docs reference real commands**

Run:

```powershell
Get-Content README.md
Get-Content SETUP.md
```

Expected:

- the new setup instructions are present and consistent with the code paths

**Step 3: Commit**

Do not commit yet.

### Task 10: Run Full Verification And Commit

**Files:**
- Modify if needed: `benchmark-results/benchmark-summary.json`
- Modify if needed: `benchmark-results/benchmark-runs.csv`
- Modify if needed: `benchmark-results/benchmark-runs.jsonl`

**Step 1: Run focused adapter tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_retrieval_live_config.py tests/test_live_search_discovery.py tests/test_live_browser_fetch.py tests/test_academic_live_adapters.py tests/test_industry_live_adapter.py tests/test_policy_live_adapters.py -q
```

Expected:

- PASS

**Step 2: Run the broader regression suite**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_retrieval_integration.py tests/test_api_answer_endpoint.py tests/test_api_runtime_benchmark.py tests/test_answer_integration.py -q
```

Expected:

- PASS

**Step 3: Run the full suite**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

Expected:

- PASS

**Step 4: Run the benchmark harness**

Run:

```powershell
python .\scripts\run_benchmark.py --cases tests/fixtures/benchmark_phase5_cases.json --runs 1 --output-dir benchmark-results
```

Expected:

- benchmark completes
- latency increases relative to fixture-only mode, but the harness still produces valid reports

**Step 5: Commit**

```powershell
git add -- pyproject.toml README.md SETUP.md skill\api\entry.py skill\config\retrieval.py skill\config\live_retrieval.py skill\retrieval\adapters\academic_semantic_scholar.py skill\retrieval\adapters\academic_arxiv.py skill\retrieval\adapters\industry_ddgs.py skill\retrieval\adapters\policy_official_registry.py skill\retrieval\adapters\policy_official_web_allowlist.py skill\retrieval\live tests docs\plans\2026-04-14-live-retrieval-adapters-design.md docs\plans\2026-04-14-live-retrieval-adapters.md benchmark-results
git commit -m "feat: add live retrieval adapters"
```
