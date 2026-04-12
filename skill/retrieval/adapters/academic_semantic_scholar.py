"""Semantic Scholar adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "academic_semantic_scholar"
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "Evidence normalization for retrieval grounded systems",
        "url": "https://www.semanticscholar.org/paper/abc123",
        "snippet": "Peer-reviewed study on merging policy and academic evidence signals.",
        "doi": "10.48550/wasc.2025.001",
        "first_author": "Lin",
        "year": 2025,
        "evidence_level": "peer_reviewed",
    },
    {
        "title": "Survey of neural information retrieval systems",
        "url": "https://www.semanticscholar.org/paper/def456",
        "snippet": "Comprehensive review of neural retrieval techniques.",
        "doi": "10.1145/1234567.8901234",
        "first_author": "Patel",
        "year": 2024,
        "evidence_level": "survey_or_review",
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
            first_author=str(item["first_author"]),
            year=int(item["year"]),
            evidence_level=str(item["evidence_level"]),
        )
        for item in ranked
    ]
