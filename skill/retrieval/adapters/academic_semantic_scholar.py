"""Semantic Scholar adapter with deterministic scholarly fixtures."""

from __future__ import annotations

import asyncio
from typing import Any

from skill.retrieval.adapters.academic_live_common import (
    academic_upstream_query,
    academic_fixture_shortcut_allowed,
    rank_live_academic_records,
)
from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients import academic_api
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "academic_semantic_scholar"
_MIN_FIXTURE_SCORE = 6
_PRIMARY_API_TIMEOUT_SECONDS = 1.4
_OPENALEX_TIMEOUT_SECONDS = 1.5
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "RAG Chunking Survey: Recent Papers and Benchmarks",
        "url": "https://www.semanticscholar.org/paper/rag-chunking-survey-2026",
        "snippet": "Survey paper reviews recent RAG chunking methods, benchmark settings, and evaluation tradeoffs.",
        "doi": "10.48550/wasc.2026.101",
        "first_author": "Wang",
        "year": 2026,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "Retrieval Reranking Benchmarks: Recent Papers",
        "url": "https://www.semanticscholar.org/paper/retrieval-reranking-benchmarks-2026",
        "snippet": "Peer-reviewed benchmark paper comparing recent retrieval reranking approaches.",
        "doi": "10.48550/wasc.2026.102",
        "first_author": "Singh",
        "year": 2026,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "LLM Agent Planning Research Review",
        "url": "https://www.semanticscholar.org/paper/llm-agent-planning-research-review",
        "snippet": "Peer-reviewed paper surveys recent LLM agent planning research and evaluation trends.",
        "doi": "10.48550/wasc.2026.103",
        "first_author": "Liu",
        "year": 2026,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "Evidence normalization for retrieval grounded systems",
        "url": "https://www.semanticscholar.org/paper/abc123",
        "snippet": "Peer-reviewed multi-source evidence ranking benchmark for grounded retrieval systems.",
        "doi": "10.48550/wasc.2025.001",
        "first_author": "Lin",
        "year": 2025,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "Grounded search evidence packing",
        "url": "https://www.semanticscholar.org/paper/grounded-search-evidence-packing",
        "snippet": "Grounded search evidence packing for bounded contexts.",
        "doi": "10.1000/grounded-search.2026.001",
        "arxiv_id": "2604.77777",
        "first_author": "Chen",
        "year": 2026,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "Export controls and academic AI chip research",
        "url": "https://www.semanticscholar.org/paper/export-controls-ai-chip-research",
        "snippet": "Export controls reshape academic research on AI chip systems.",
        "doi": "10.1000/export-controls.2026.001",
        "first_author": "Zhang",
        "year": 2026,
        "evidence_level": "peer_reviewed",
    },
)


def _score(query: str, fixture: dict[str, Any]) -> int:
    return score_query_alignment(
        query,
        route="academic",
        title=str(fixture["title"]),
        snippet=str(fixture["snippet"]),
        url=str(fixture["url"]),
        year=int(fixture["year"]),
    )


async def search_fixture(query: str) -> list[RetrievalHit]:
    """Return deterministic scholarly results for offline tests."""
    ranked = sorted(
        _FIXTURES,
        key=lambda item: (_score(query, item), item["url"]),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            doi=str(item["doi"]),
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]),
            year=int(item["year"]),
            evidence_level=str(item["evidence_level"]),
        )
        for item in ranked
    ]


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live scholarly results from Semantic Scholar."""
    config = LiveRetrievalConfig.from_env()
    upstream_query = academic_upstream_query(query)
    if config.fixture_shortcuts_enabled:
        fixture_hits = [
            hit
            for hit in await search_fixture(query)
            if academic_fixture_shortcut_allowed(
                query=query,
                title=hit.title,
                snippet=hit.snippet,
                url=hit.url,
                year=hit.year,
            )
        ]
        if fixture_hits:
            return fixture_hits[:3]

    openalex_task = asyncio.create_task(
        academic_api.search_openalex(query=upstream_query, max_results=5)
    )
    try:
        records = await asyncio.wait_for(
            academic_api.search_semantic_scholar(query=upstream_query, max_results=5),
            timeout=_PRIMARY_API_TIMEOUT_SECONDS,
        )
    except Exception:
        records = []
    ranked_records = rank_live_academic_records(
        query=query,
        records=records,
        max_results=5,
    )
    hits = [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            doi=str(item["doi"]) if item.get("doi") is not None else None,
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in ranked_records
    ]
    if hits:
        if not openalex_task.done():
            openalex_task.cancel()
            await asyncio.gather(openalex_task, return_exceptions=True)
        return hits

    try:
        openalex_records = await asyncio.wait_for(
            openalex_task,
            timeout=_OPENALEX_TIMEOUT_SECONDS,
        )
    except Exception:
        openalex_records = []
    ranked_openalex_records = rank_live_academic_records(
        query=query,
        records=openalex_records,
        max_results=5,
    )
    openalex_hits = [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            doi=str(item["doi"]) if item.get("doi") is not None else None,
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in ranked_openalex_records
    ]
    if openalex_hits:
        return openalex_hits

    return []


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
