# WASC High-Precision Search Skill

Low-cost, high-precision search Skill for WASC competition tasks across policy/regulation, industry information, academic literature, and mixed-domain queries.

## Why This Project

This repository ships a browser-free search pipeline designed for the WASC April challenge. It focuses on three things that matter in the competition:

- grounded answers instead of unsupported synthesis
- low latency and bounded token usage
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

- Full test suite: `172 passed`
- Phase 4 answer-focused suite: `33 passed`

Latest live benchmark artifact:

- File: [`./benchmark-results/benchmark-summary.json`](./benchmark-results/benchmark-summary.json)
- `total_runs: 50`
- `successful_runs: 50`
- `success_rate: 1.0`
- `answer_status_breakdown.grounded_success: 50`
- `latency_p50_ms: 1`
- `latency_p95_ms: 1`
- `latency_budget_pass_rate: 1.0`
- `token_budget_pass_rate: 1.0`

## Capability Summary

### Supported Query Families

- policy/regulation
- industry information
- academic literature
- mixed-domain benchmark queries

### Core Behaviors

- deterministic routing with browser automation disabled
- concurrent multi-source retrieval with bounded fallback behavior
- canonical evidence normalization and deduplication before synthesis
- grounded answer generation with citation validation
- explicit answer states: `grounded_success`, `insufficient_evidence`, `retrieval_failure`
- request-scoped runtime budgets for `/answer`
- repeatable `10 x 5` benchmark execution with JSONL, CSV, and summary artifacts

### Explicit Non-Goals

- Playwright or browser automation in the main path
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

### 3. Export the MiniMax credential

The live `/answer` path reads either `MINIMAX_API_KEY` or `MINIMAX_KEY`.

PowerShell:

```powershell
$env:MINIMAX_KEY="your-minimax-key"
```

### 4. Start the API

```powershell
uvicorn skill.api.entry:app --host 0.0.0.0 --port 8000
```

### 5. Try the endpoints

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

## Competition Fit

This project is aligned to the WASC competition constraints captured in the local competition brief file included in the repository:

- browser-free core path
- support for policy, industry, and academic tasks
- structured, judge-readable output
- repeatability over repeated benchmark runs
- compatibility with MiniMax-based live answer generation

## Known Limitations

- The live `/answer` path requires a valid MiniMax key in the environment.
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
