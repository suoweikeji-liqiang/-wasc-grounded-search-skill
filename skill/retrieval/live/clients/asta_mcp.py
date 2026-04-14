"""Asta Scientific Corpus MCP client helpers."""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Mapping

import httpx

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.parsers.academic import parse_asta_search_result

_DEFAULT_ENDPOINT = "https://asta-tools.allen.ai/mcp/v1"
_DEFAULT_TIMEOUT_SECONDS = 2.5
_REQUEST_IDS = itertools.count(1)
_SEARCH_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)


def _api_key() -> str | None:
    for env_name in (
        "WASC_ASTA_MCP_API_KEY",
        "S2_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
    ):
        value = (os.getenv(env_name) or "").strip()
        if value:
            return value
    return None


def _endpoint() -> str:
    return (os.getenv("WASC_ASTA_MCP_ENDPOINT") or _DEFAULT_ENDPOINT).strip()


def _timeout_seconds() -> float:
    raw = (os.getenv("WASC_ASTA_MCP_TIMEOUT_SECONDS") or "").strip()
    if not raw:
        return _DEFAULT_TIMEOUT_SECONDS
    return float(raw)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"{query.strip().lower()}|{max(1, max_results)}"


def _request_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "WASC-clean/1.0",
    }
    api_key = _api_key()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


async def _call_tool(
    *,
    name: str,
    arguments: Mapping[str, object],
    timeout_seconds: float,
) -> object:
    payload = {
        "jsonrpc": "2.0",
        "id": next(_REQUEST_IDS),
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": dict(arguments),
        },
    }

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        async with client.stream(
            "POST",
            _endpoint(),
            headers=_request_headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            event_lines: list[str] = []
            async for line in response.aiter_lines():
                if line == "":
                    parsed = _parse_sse_event(event_lines)
                    if parsed is not None:
                        return parsed
                    event_lines = []
                    continue
                event_lines.append(line)

    parsed = _parse_sse_event(event_lines)
    if parsed is not None:
        return parsed
    raise RuntimeError("Asta MCP response did not contain a JSON-RPC data event")


def _parse_sse_event(lines: list[str]) -> object | None:
    if not lines:
        return None
    data_lines = [
        line[6:]
        for line in lines
        if line.startswith("data: ")
    ]
    if not data_lines:
        return None
    payload = json.loads("\n".join(data_lines))
    if not isinstance(payload, dict):
        raise RuntimeError("Asta MCP returned a non-object JSON-RPC payload")
    if payload.get("error") is not None:
        raise RuntimeError(str(payload["error"]))
    if "result" not in payload:
        raise RuntimeError("Asta MCP JSON-RPC payload missing result")
    return payload["result"]


async def _search_papers_uncached(
    *,
    query: str,
    max_results: int,
) -> list[dict[str, object]]:
    timeout_seconds = _timeout_seconds()
    title_result = await _call_tool(
        name="search_paper_by_title",
        arguments={
            "title": query,
            "fields": "abstract,authors,url,venue,year,tldr",
        },
        timeout_seconds=timeout_seconds,
    )
    return parse_asta_search_result(title_result)[:max_results]


async def search_papers(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _SEARCH_CACHE.get(key)
    if cached is not None:
        return cached
    hits = await _search_papers_uncached(query=query, max_results=max_results)
    _SEARCH_CACHE.set(
        key,
        hits,
        ttl_seconds=config.academic_cache_ttl_seconds,
    )
    return hits
