"""Observable industry official-or-filings adapter."""

from __future__ import annotations

from skill.retrieval.adapters import industry_ddgs as _shared


async def search_fixture(query: str):
    return await _shared.search_official_or_filings_fixture(query)


async def search_live(query: str):
    return await _shared.search_official_or_filings_live(query)


async def search(query: str):
    return await search_fixture(query)
