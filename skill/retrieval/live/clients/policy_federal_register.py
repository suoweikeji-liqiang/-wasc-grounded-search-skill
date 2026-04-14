"""Official Federal Register search client."""

from __future__ import annotations

import re

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.clients import http as http_client

_SEARCH_ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_TAG_RE = re.compile(r"<[^>]+>")


def _cache_key(query: str, *, max_results: int) -> str:
    return f"fr|{query.strip().lower()}|{max(1, max_results)}"


def _clean_html_text(value: object | None) -> str:
    if value in (None, ""):
        return ""
    return " ".join(_TAG_RE.sub("", str(value)).split())


def _version_from_result(result: dict[str, object]) -> str | None:
    document_type = result.get("type")
    document_number = result.get("document_number")
    parts = [str(document_type).strip() if document_type else "", str(document_number).strip() if document_number else ""]
    version = " ".join(part for part in parts if part)
    return version or None


async def search_federal_register(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    payload = await http_client.fetch_json(
        url=_SEARCH_ENDPOINT,
        params={
            "conditions[term]": query,
            "per_page": str(max(1, max_results)),
            "order": "relevance",
        },
        timeout=2.5,
    )
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    parsed: list[dict[str, object]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("html_url") or "").strip()
        if not title or not url:
            continue
        agencies = item.get("agencies")
        authority = None
        if isinstance(agencies, list) and agencies:
            first_agency = agencies[0]
            if isinstance(first_agency, dict):
                authority = (
                    str(first_agency.get("name") or "").strip()
                    or str(first_agency.get("raw_name") or "").strip()
                    or None
                )
        snippet = _clean_html_text(item.get("abstract")) or _clean_html_text(item.get("excerpts")) or title
        parsed.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "authority": authority,
                "jurisdiction": "US",
                "publication_date": str(item.get("publication_date") or "").strip() or None,
                "effective_date": (
                    str(item.get("effective_on") or "").strip()
                    or str(item.get("effective_date") or "").strip()
                    or None
                ),
                "version": _version_from_result(item),
            }
        )

    clipped = parsed[: max(1, max_results)]
    _CACHE.set(key, clipped, ttl_seconds=config.search_cache_ttl_seconds)
    return clipped
