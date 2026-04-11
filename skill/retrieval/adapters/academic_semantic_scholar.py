"""Semantic Scholar adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "academic_semantic_scholar"
_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "Dense retrieval with adaptive negative sampling",
        "url": "https://www.semanticscholar.org/paper/abc123",
        "snippet": "Peer-reviewed retrieval work with benchmark comparisons.",
    },
    {
        "title": "Survey of neural information retrieval systems",
        "url": "https://www.semanticscholar.org/paper/def456",
        "snippet": "Comprehensive review of neural retrieval techniques.",
    },
)


def _score(query: str, fixture: dict[str, str]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((fixture["title"], fixture["snippet"])).lower()
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
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
        )
        for item in ranked
    ]
