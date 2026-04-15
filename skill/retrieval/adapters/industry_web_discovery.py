"""Observable industry web-discovery adapter."""

from __future__ import annotations

from skill.retrieval.adapters import industry_ddgs as _shared


async def search_fixture(query: str):
    return await _shared.search_web_discovery_fixture(query)


async def search_live(query: str):
    return await _shared.search_web_discovery_live(query)


async def search(query: str):
    return await search_fixture(query)
