# WASC High-Precision Search Skill

High-precision grounded search Skill for WASC competition tasks across policy/regulation, industry information, academic literature, and mixed-domain queries.

## Why This Project

This repository ships a grounded search pipeline designed for the WASC April challenge. It focuses on three things that matter in the competition:

- grounded answers instead of unsupported synthesis
- live retrieval coverage for hidden queries
- bounded latency and token usage
- repeatable behavior across repeated benchmark runs

The system exposes three structured API surfaces:

- `/route` for query classification and source-family planning
- `/retrieve` for bounded multi-source retrieval with canonical evidence
- `/answer` for grounded, citation-gated structured answers

## Verified Status

Current local release state:

- Milestone: `v1.0 Initial MVP`
- Git tag: `v1.0`
- Planning archive: [`./.planning/MILESTONES.md`](./.planning/MILESTONES.md)

Latest verified automated checks:

- Full test suite: `259 passed`
- Phase 4 answer-focused suite: `35 passed`

Sample benchmark artifact in this repository:

- File: [`./benchmark-results/benchmark-summary.json`](./benchmark-results/benchmark-summary.json)
- `total_runs: 50`
- `successful_runs: 50`
- `success_rate: 1.0`
- `answer_status_breakdown.grounded_success: 50`
- `latency_p50_ms: 1`
- `latency_p95_ms: 1`
- `latency_budget_pass_rate: 1.0`
- `token_budget_pass_rate: 1.0`

These numbers come from a prior fixture-heavy benchmark snapshot and should not be read as representative of live-retrieval latency.

## Capability Summary

### Supported Query Families

- policy/regulation
- industry information
- academic literature
- mixed-domain benchmark queries

### Core Behaviors

- deterministic routing with browser automation disabled at the API contract level
- concurrent multi-source retrieval with bounded fallback behavior
- live academic retrieval from Asta MCP, Semantic Scholar, OpenAlex, Europe PMC, and arXiv-backed paths
- multi-engine open-web discovery for industry retrieval with official SEC EDGAR supplement for filing-oriented company queries
- official-domain discovery and metadata extraction for policy retrieval with public official coverage expanded to Chinese law-library domains and the US Federal Register API
- canonical evidence normalization and deduplication before synthesis
- grounded answer generation with citation validation
- explicit answer states: `grounded_success`, `insufficient_evidence`, `retrieval_failure`
- request-scoped runtime budgets for `/answer`
- repeatable `10 x 5` benchmark execution with JSONL, CSV, and summary artifacts

### Explicit Non-Goals

- MCP or admin-platform infrastructure
- chat-first multi-step agent behavior
- heavy multi-model orchestration
- broad productization beyond the competition-focused search skill

## Repository Layout

```text
project-root/
- skill/                  # core routing, retrieval, evidence, synthesis, API, benchmark code
- scripts/                # CLI entrypoints for routing smoke tests and benchmark runs
- tests/                  # offline and endpoint-path regression coverage
- benchmark-results/      # benchmark output artifacts
- .planning/              # milestone, roadmap, verification, and archive history
- README.md
- SKILL.md
- SETUP.md
- LICENSE
```

## Quick Start

### 1. Create and activate a Python environment

PowerShell:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

### 2. Install the package

```powershell
pip install -e .[dev]
```

### 3. Optional: install the headless browser runtime

The live retrieval path can use headless Playwright as a fallback for pages that do not yield usable content over plain HTTP.

```powershell
playwright install chromium
```

### 4. Export the MiniMax credential

The live `/answer` path reads either `MINIMAX_API_KEY` or `MINIMAX_KEY`.

PowerShell:

```powershell
$env:MINIMAX_KEY="your-minimax-key"
```

### 5. Optional: configure live retrieval

Default runtime retrieval mode is `live`.

PowerShell:

```powershell
$env:WASC_RETRIEVAL_MODE="live"
$env:WASC_LIVE_BROWSER_ENABLED="0"
$env:WASC_LIVE_BROWSER_HEADLESS="1"
```

Optional Semantic Scholar credential:

```powershell
$env:SEMANTIC_SCHOLAR_API_KEY="your-semantic-scholar-key"
```

Optional Asta MCP credential for higher academic-search rate limits:

```powershell
$env:S2_API_KEY="your-semantic-scholar-or-asta-key"
```

Set `WASC_RETRIEVAL_MODE="fixture"` if you need deterministic offline adapter behavior.

### 6. Start the API

```powershell
uvicorn skill.api.entry:app --host 0.0.0.0 --port 8000
```

### 7. Try the endpoints

Route:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/route -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

Retrieve:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/retrieve -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

Answer:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

## CLI Entry Points

Route one query through the deterministic routing core:

```powershell
python .\scripts\route_query.py "evidence normalization benchmark paper"
```

Run the locked benchmark suite through the live `/answer` path:

```powershell
python .\scripts\run_benchmark.py --cases tests/fixtures/benchmark_phase5_cases.json --runs 5 --output-dir benchmark-results
```

Generated benchmark files:

- `benchmark-results/benchmark-runs.jsonl`
- `benchmark-results/benchmark-runs.csv`
- `benchmark-results/benchmark-summary.json`

## API Contract Overview

### `POST /route`

Input:

```json
{"query":"..."}
```

Output shape:

- `route_label`
- `source_families`
- `primary_route`
- `supplemental_route`
- `browser_automation`

### `POST /retrieve`

Output adds:

- retrieval `status`
- `failure_reason`
- `gaps`
- `results`
- `canonical_evidence`
- `evidence_clipped`
- `evidence_pruned`

### `POST /answer`

Output adds:

- `answer_status`
- `retrieval_status`
- `conclusion`
- `key_points`
- `sources`
- `uncertainty_notes`
- `gaps`

The public answer contract intentionally does not expose internal runtime telemetry.

## Testing And Verification

Run the full suite:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

Run the answer-focused suite:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py tests/test_answer_generator.py tests/test_answer_citation_check.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q
```

## Runtime Controls

The `/answer` path reads these runtime budget environment variables:

- `WASC_REQUEST_DEADLINE_SECONDS`
- `WASC_SYNTHESIS_DEADLINE_SECONDS`
- `WASC_ANSWER_TOKEN_BUDGET`

Defaults in code:

- request deadline: `8.0` seconds
- synthesis deadline: `2.0` seconds
- answer token budget: `1200`

Live retrieval also reads:

- `WASC_RETRIEVAL_MODE`
- `WASC_LIVE_SEARCH_ENGINES`
- `WASC_LIVE_BROWSER_ENABLED`
- `WASC_LIVE_BROWSER_HEADLESS`
- `WASC_LIVE_SEARCH_CACHE_TTL_SECONDS`
- `WASC_LIVE_PAGE_CACHE_TTL_SECONDS`
- `WASC_LIVE_ACADEMIC_CACHE_TTL_SECONDS`
- `WASC_ASTA_MCP_API_KEY`
- `WASC_ASTA_MCP_ENDPOINT`
- `WASC_ASTA_MCP_TIMEOUT_SECONDS`
- `S2_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`

## Competition Fit

This project is aligned to the WASC competition constraints captured in the local competition brief file included in the repository:

- grounded retrieval with live coverage for unknown policy, academic, and industry queries
- support for policy, industry, and academic tasks
- structured, judge-readable output
- repeatability over repeated benchmark runs
- compatibility with MiniMax-based live answer generation

## Known Limitations

- The live `/answer` path requires a valid MiniMax key in the environment.
- Live retrieval depends on network reachability for the configured sources.
- Headless browser fallback requires `playwright install chromium` if enabled.
- The project archive still carries two advisory debts from the `v1.0` audit.
- No demo video or screen recording is included in this repository yet.

## Demo Suggestion

For submission packaging, the recommended demo is a short recording that shows:

1. starting the API
2. calling `/answer` with one policy, one academic, and one mixed query
3. running the benchmark CLI and opening `benchmark-summary.json`

## Additional Project Records

- Skill definition: [`./SKILL.md`](./SKILL.md)
- Setup guide: [`./SETUP.md`](./SETUP.md)
- Project archive: [`./.planning/PROJECT.md`](./.planning/PROJECT.md)
- Retrospective: [`./.planning/RETROSPECTIVE.md`](./.planning/RETROSPECTIVE.md)
