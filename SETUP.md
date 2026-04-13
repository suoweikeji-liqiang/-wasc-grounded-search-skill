# Setup Guide

This guide explains how to run the WASC High-Precision Search Skill locally for API testing, benchmark execution, and competition review.

## Requirements

- Python `3.12+`
- PowerShell or another shell able to export environment variables
- network access for live MiniMax-backed `/answer` runs

## Install

### 1. Create a virtual environment

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

### 2. Install project dependencies

```powershell
pip install -e .[dev]
```

## Environment Variables

### Required For Live `/answer`

Set one of:

- `MINIMAX_API_KEY`
- `MINIMAX_KEY`

Example:

```powershell
$env:MINIMAX_KEY="your-minimax-key"
```

### Optional Runtime Budget Overrides

```powershell
$env:WASC_REQUEST_DEADLINE_SECONDS="8.0"
$env:WASC_SYNTHESIS_DEADLINE_SECONDS="2.0"
$env:WASC_ANSWER_TOKEN_BUDGET="1200"
```

Notes:

- the code reads environment variables directly with `os.getenv(...)`
- a local `.env` file is not auto-loaded by the app
- if you keep secrets in `.env`, you still need to export them into the current shell before starting the server

## Start The API

```powershell
uvicorn skill.api.entry:app --host 0.0.0.0 --port 8000
```

Available endpoints:

- `POST /route`
- `POST /retrieve`
- `POST /answer`

## Example Requests

### Route

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/route -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

### Retrieve

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/retrieve -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

### Answer

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

## CLI Workflows

### Route smoke test

```powershell
python .\scripts\route_query.py "evidence normalization benchmark paper"
```

### Locked benchmark suite

```powershell
python .\scripts\run_benchmark.py --cases tests/fixtures/benchmark_phase5_cases.json --runs 5 --output-dir benchmark-results
```

Artifacts written to `benchmark-results/`:

- `benchmark-runs.jsonl`
- `benchmark-runs.csv`
- `benchmark-summary.json`

## Test Commands

### Full suite

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

### Answer path coverage

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_answer_contracts.py tests/test_answer_state_mapping.py tests/test_answer_generator.py tests/test_answer_citation_check.py tests/test_answer_integration.py tests/test_api_answer_endpoint.py -q
```

### Benchmark path coverage

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests/test_benchmark_repeatability.py tests/test_api_runtime_benchmark.py -q
```

## Benchmark Review

The benchmark harness runs against the live FastAPI `/answer` surface and writes structured reports.

The current repository already includes a verified sample artifact:

- `benchmark-results/benchmark-summary.json`

Latest recorded values in this workspace:

- `total_runs: 50`
- `successful_runs: 50`
- `success_rate: 1.0`
- `latency_p50_ms: 1`
- `latency_p95_ms: 1`
- `latency_budget_pass_rate: 1.0`
- `token_budget_pass_rate: 1.0`

## Troubleshooting

### `MiniMaxTextClient requires a non-empty api_key`

Cause:

- no `MINIMAX_API_KEY` or `MINIMAX_KEY` exported in the current shell

Fix:

```powershell
$env:MINIMAX_KEY="your-minimax-key"
```

### `.env` exists but `/answer` still cannot see the key

Cause:

- the app does not load `.env` automatically

Fix:

- export the variable in the shell before starting `uvicorn`

### I only want offline verification

Use:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q
```

This exercises the deterministic regression suite without requiring a live provider call for every test.

### Benchmark files were not created

Check:

- the API app started successfully inside the benchmark process
- the output directory path is writable
- the run did not fail before `write_benchmark_reports(...)`

## Submission Notes

For WASC-style submission packaging, this repository now includes:

- `README.md`
- `SKILL.md`
- `SETUP.md`
- `tests/`
- `skill/`
- `LICENSE`

A demo video link can be added later without changing the runtime or API contracts.

