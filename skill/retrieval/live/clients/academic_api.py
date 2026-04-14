"""Live academic source clients."""

from __future__ import annotations

import os

from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.academic import (
    parse_arxiv_feed,
    parse_semantic_scholar_response,
)


SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL = "https://export.arxiv.org/api/query"


async def search_semantic_scholar(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    headers: dict[str, str] = {}
    api_key = (os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    payload = await http_client.fetch_json(
        url=SEMANTIC_SCHOLAR_API_URL,
        params={
            "query": query,
            "limit": str(max(1, max_results)),
            "fields": "title,abstract,url,authors,year,externalIds",
        },
        headers=headers or None,
        timeout=10.0,
    )
    return parse_semantic_scholar_response(payload)


async def search_arxiv(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    xml_text = await http_client.fetch_text(
        url=ARXIV_API_URL,
        params={
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(max(1, max_results)),
            "sortBy": "relevance",
            "sortOrder": "descending",
        },
        timeout=10.0,
    )
    return parse_arxiv_feed(xml_text)
