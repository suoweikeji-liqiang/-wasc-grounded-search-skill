"""arXiv adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "academic_arxiv"
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "Evidence normalization for retrieval grounded systems preprint",
        "url": "https://arxiv.org/abs/2604.12345",
        "snippet": "Preprint variant of the evidence normalization study before journal publication.",
        "arxiv_id": "2604.12345",
        "first_author": "Lin",
        "year": 2025,
        "evidence_level": "preprint",
    },
    {
        "title": "Multi-source evidence ranking with constrained latency",
        "url": "https://arxiv.org/abs/2603.54321",
        "snippet": "Latency-aware retrieval strategy for benchmark-oriented QA.",
        "arxiv_id": "2603.54321",
        "first_author": "Garcia",
        "year": 2026,
        "evidence_level": "preprint",
    },
)


def _score(query: str, fixture: dict[str, Any]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((str(fixture["title"]), str(fixture["snippet"]))).lower()
    return sum(1 for token in tokens if token in haystack)


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
