"""Live academic source clients."""

from __future__ import annotations

import os

from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.academic import (
    parse_arxiv_feed,
    parse_europe_pmc_response,
    parse_openalex_response,
    parse_semantic_scholar_response,
)
from skill.orchestrator.normalize import normalize_query_text


SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
OPENALEX_API_URL = "https://api.openalex.org/works"
EUROPE_PMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _contact_email() -> str:
    return (
        os.getenv("WASC_CONTACT_EMAIL", "")
        or os.getenv("OPENALEX_MAILTO", "")
        or os.getenv("CROSSREF_MAILTO", "")
    ).strip()


def _cache_key(provider: str, *, query: str, max_results: int) -> str:
    normalized_query = normalize_query_text(query)
    return f"{provider}:{normalized_query}:limit={max(1, max_results)}"


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
        cache_scope="academic",
        cache_key=_cache_key(
            "semantic_scholar",
            query=query,
            max_results=max_results,
        ),
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
        cache_scope="academic",
        cache_key=_cache_key(
            "arxiv",
            query=query,
            max_results=max_results,
        ),
    )
    return parse_arxiv_feed(xml_text)


async def search_openalex(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    params = {
        "search": query,
        "per-page": str(max(1, max_results)),
        "select": (
            "id,doi,title,display_name,publication_year,authorships,"
            "primary_location,best_oa_location,abstract_inverted_index,type"
        ),
    }
    mailto = _contact_email()
    if mailto:
        params["mailto"] = mailto
    payload = await http_client.fetch_json(
        url=OPENALEX_API_URL,
        params=params,
        timeout=10.0,
        cache_scope="academic",
        cache_key=_cache_key(
            "openalex",
            query=query,
            max_results=max_results,
        ),
    )
    return parse_openalex_response(payload)


async def search_europe_pmc(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    payload = await http_client.fetch_json(
        url=EUROPE_PMC_API_URL,
        params={
            "query": query,
            "format": "json",
            "pageSize": str(max(1, max_results)),
            "resultType": "lite",
        },
        timeout=10.0,
        cache_scope="academic",
        cache_key=_cache_key(
            "europe_pmc",
            query=query,
            max_results=max_results,
        ),
    )
    return parse_europe_pmc_response(payload)
