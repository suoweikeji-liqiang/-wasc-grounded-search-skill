"""Semantic Scholar adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "academic_semantic_scholar"
_FIXTURES: tuple[dict[str, Any], ...] = (
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
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((str(fixture["title"]), str(fixture["snippet"]))).lower()
    return sum(1 for token in tokens if token in haystack)


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
