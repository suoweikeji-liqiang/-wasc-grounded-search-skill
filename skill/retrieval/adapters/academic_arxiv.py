"""arXiv adapter with deterministic scholarly fixtures."""

from __future__ import annotations

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "academic_arxiv"
_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "Efficient retrieval augmentation for compact language models",
        "url": "https://arxiv.org/abs/2604.12345",
        "snippet": "Preprint describing retrieval-grounded generation methods.",
    },
    {
        "title": "Multi-source evidence ranking with constrained latency",
        "url": "https://arxiv.org/abs/2603.54321",
        "snippet": "Latency-aware retrieval strategy for benchmark-oriented QA.",
    },
)


def _score(query: str, fixture: dict[str, str]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((fixture["title"], fixture["snippet"])).lower()
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
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
        )
        for item in ranked
    ]
