"""Semantic Scholar adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "academic_semantic_scholar"
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
        "snippet": "Peer-reviewed evidence normalization benchmark for grounded retrieval.",
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


async def search(query: str) -> list[RetrievalHit]:
    """Return scholarly results tied to Semantic Scholar source identity."""
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
