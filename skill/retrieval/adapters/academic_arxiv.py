"""arXiv adapter with deterministic scholarly fixtures."""

from __future__ import annotations

import re
from typing import Any

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients import academic_api
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "academic_arxiv"
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "Recent RAG Chunking Benchmark Paper",
        "url": "https://arxiv.org/abs/2605.11001",
        "snippet": "arXiv paper compares recent chunking strategies for retrieval-augmented generation benchmarks.",
        "arxiv_id": "2605.11001",
        "first_author": "Zhao",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Recent Benchmark Paper for Neural Retrieval Reranking",
        "url": "https://arxiv.org/abs/2605.11002",
        "snippet": "arXiv benchmark paper on cross-encoder and late-interaction retrieval reranking.",
        "arxiv_id": "2605.11002",
        "first_author": "Patel",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Recent Papers on LLM Agent Planning",
        "url": "https://arxiv.org/abs/2605.11003",
        "snippet": "arXiv paper studies planning-aware agents, tool use, and recent LLM agent planning methods.",
        "arxiv_id": "2605.11003",
        "first_author": "Kim",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Evidence normalization for retrieval grounded systems preprint",
        "url": "https://arxiv.org/abs/2604.12345",
        "snippet": "Evidence normalization benchmark preprint for retrieval.",
        "arxiv_id": "2604.12345",
        "first_author": "Lin",
        "year": 2025,
        "evidence_level": "preprint",
    },
    {
        "title": "Grounded search evidence packing preprint",
        "url": "https://arxiv.org/abs/2604.77777",
        "snippet": "Grounded search evidence packing preprint for bounded contexts.",
        "arxiv_id": "2604.77777",
        "first_author": "Chen",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Multi-source evidence ranking with constrained latency",
        "url": "https://arxiv.org/abs/2603.54321",
        "snippet": "Latency-aware retrieval benchmark preprint.",
        "arxiv_id": "2603.54321",
        "first_author": "Garcia",
        "year": 2026,
        "evidence_level": "preprint",
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
            arxiv_id=str(item["arxiv_id"]),
            first_author=str(item["first_author"]),
            year=int(item["year"]),
            evidence_level=str(item["evidence_level"]),
        )
        for item in ranked
    ]


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live scholarly results from arXiv."""
    try:
        records = await academic_api.search_arxiv(query=query, max_results=5)
    except Exception:
        records = []
    hits = [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in records
        if item.get("title") and item.get("url")
    ]
    if hits:
        return hits

    config = LiveRetrievalConfig.from_env()
    try:
        candidates = await search_multi_engine(
            query=f"{query} site:arxiv.org",
            engines=config.search_engines,
            max_results=5,
        )
    except Exception:
        return []

    fallback_hits: list[RetrievalHit] = []
    for candidate in candidates:
        arxiv_match = _ARXIV_ID_RE.search(candidate.url)
        if arxiv_match is None:
            continue
        arxiv_id = arxiv_match.group(1)
        year_prefix = arxiv_id[:2]
        year = 2000 + int(year_prefix) if year_prefix.isdigit() else None
        fallback_hits.append(
            RetrievalHit(
                source_id=_SOURCE_ID,
                title=candidate.title,
                url=candidate.url,
                snippet=candidate.snippet,
                arxiv_id=arxiv_id,
                year=year,
                evidence_level="preprint",
            )
        )
    return fallback_hits


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
