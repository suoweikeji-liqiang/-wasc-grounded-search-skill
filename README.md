# WASC High-Precision Search Skill

Grounded search Skill for low-cost, high-precision retrieval across:

- policy / regulation
- industry / company / standards
- academic literature
- mixed policy + industry / policy + academic queries

## What It Does

The repository exposes three public API surfaces:

- `POST /route`
- `POST /retrieve`
- `POST /answer`

The system is designed to:

- route a query to the right source family
- retrieve bounded, source-backed evidence
- normalize evidence into canonical records
- return structured answers with citations and explicit answer states

## Delivery Contents

This repository is cleaned for delivery around the runnable Skill implementation:

- [SKILL.md](./SKILL.md)
- [SETUP.md](./SETUP.md)
- [submit-template.txt](./submit-template.txt)
- [examples/README.md](./examples/README.md)
- `skill/`
- `scripts/`
- `tests/`
- [LICENSE](./LICENSE)

## Key Behaviors

- grounded structured answers instead of unsupported free-form synthesis
- live retrieval with bounded runtime budgets
- official-source preference for policy and filing / standards queries
- mixed-query handling with explicit partial-answer behavior when only one side is supported
- explicit answer states:
  - `grounded_success`
  - `insufficient_evidence`
  - `retrieval_failure`

## Quick Start

Create and activate an environment:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Optional browser fallback:

```powershell
playwright install chromium
```

Set the MiniMax credential for live `/answer`:

```powershell
$env:MINIMAX_KEY="your-minimax-key"
```

Recommended live retrieval defaults:

```powershell
$env:WASC_RETRIEVAL_MODE="live"
$env:WASC_LIVE_BROWSER_ENABLED="0"
$env:WASC_LIVE_BROWSER_HEADLESS="1"
```

Disk cache is disabled by default for self-serve use so the Skill does not keep growing local cache directories.
Enable it only when you explicitly want persistent cross-process cache reuse:

```powershell
$env:WASC_LIVE_DISK_CACHE_ENABLED="1"
```

Start the API:

```powershell
uvicorn skill.api.entry:app --host 0.0.0.0 --port 8000
```

## Minimal Usage

Route one query:

```powershell
python .\scripts\route_query.py "evidence normalization benchmark paper"
```

Call the API directly:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

More reproducible examples are in [examples/README.md](./examples/README.md).

## Runtime Controls

Main runtime controls:

- `WASC_RETRIEVAL_MODE`
- `WASC_LIVE_SEARCH_ENGINES`
- `WASC_LIVE_BROWSER_ENABLED`
- `WASC_LIVE_BROWSER_HEADLESS`
- `WASC_LIVE_DISK_CACHE_ENABLED`
- `WASC_LIVE_SEARCH_CACHE_TTL_SECONDS`
- `WASC_LIVE_PAGE_CACHE_TTL_SECONDS`
- `WASC_LIVE_ACADEMIC_CACHE_TTL_SECONDS`
- `WASC_REQUEST_DEADLINE_SECONDS`
- `WASC_SYNTHESIS_DEADLINE_SECONDS`
- `WASC_ANSWER_TOKEN_BUDGET`

Optional academic-source credentials:

- `S2_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`
- `WASC_ASTA_MCP_API_KEY`
- `WASC_ASTA_MCP_ENDPOINT`
- `WASC_ASTA_MCP_TIMEOUT_SECONDS`

## Testing

Run the full local suite:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

Run a lightweight smoke subset:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_retrieval_live_config.py tests/test_live_http_client.py tests/test_answer_guardrails.py -q
```

## Submission Notes

According to the submission page, the core deliverables are:

- public GitHub repository
- complete README and run instructions
- Skill implementation files
- test / example material with reproducible steps
- public demo / video link

The repository now includes the first four.
The demo link still needs to be supplied manually at submission time.

The official mail template is copied to [submit-template.txt](./submit-template.txt).
