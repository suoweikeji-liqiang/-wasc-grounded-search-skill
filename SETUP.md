# Setup Guide

This guide explains how to run the Skill locally for review and reproduction.

## Requirements

- Python `3.12+`
- network access for live retrieval
- MiniMax key for live `/answer`

## Install

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Optional browser fallback:

```powershell
playwright install chromium
```

## Required Environment

```powershell
$env:MINIMAX_KEY="your-minimax-key"
$env:WASC_RETRIEVAL_MODE="live"
$env:WASC_LIVE_BROWSER_ENABLED="0"
$env:WASC_LIVE_BROWSER_HEADLESS="1"
```

Optional academic source credentials:

```powershell
$env:S2_API_KEY="your-key"
$env:SEMANTIC_SCHOLAR_API_KEY="your-key"
```

Disk cache is disabled by default.
Enable it only if you explicitly want persistent cross-process cache reuse:

```powershell
$env:WASC_LIVE_DISK_CACHE_ENABLED="1"
```

## Start The API

```powershell
uvicorn skill.api.entry:app --host 0.0.0.0 --port 8000
```

## Minimal Reproduction

Route:

```powershell
python .\scripts\route_query.py "evidence normalization benchmark paper"
```

Answer:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer -ContentType 'application/json' -Body '{"query":"evidence normalization benchmark paper"}'
```

More examples are in [examples/README.md](./examples/README.md).

## Optional Tests

Full suite:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

Compact verification subset:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_retrieval_live_config.py tests/test_live_http_client.py tests/test_answer_guardrails.py -q
```
