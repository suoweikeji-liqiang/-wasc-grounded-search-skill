"""arXiv adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "academic_arxiv"
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


async def search(query: str) -> list[RetrievalHit]:
    """Return scholarly results tied to arXiv source identity."""
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
