"""Direct official UK legislation source client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_UK_MARKERS: tuple[str, ...] = (
    "uk",
    "united kingdom",
    "legislation.gov.uk",
    "online safety act",
    "ofcom",
)
_CATALOG: tuple[dict[str, object], ...] = (
    {
        "title": "Online Safety Act 2023",
        "url": "https://www.legislation.gov.uk/ukpga/2023/50/contents",
        "snippet": "Official UK legislation text for the Online Safety Act 2023.",
        "authority": "UK legislation",
        "jurisdiction": "UK",
        "publication_date": "2023-10-26",
        "effective_date": None,
        "version": "As enacted",
        "markers": ("online safety act", "ukpga/2023/50", "illegal content duties", "ofcom codes"),
    },
    {
        "title": "Data Protection Act 2018",
        "url": "https://www.legislation.gov.uk/ukpga/2018/12/contents",
        "snippet": "Official UK legislation text for the Data Protection Act 2018.",
        "authority": "UK legislation",
        "jurisdiction": "UK",
        "publication_date": "2018-05-23",
        "effective_date": None,
        "version": "As enacted",
        "markers": ("data protection act", "ukpga/2018/12", "dpa 2018"),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"uk-legislation|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    markers = tuple(str(item).lower() for item in record.get("markers", ()))
    marker_hits = sum(1 for marker in markers if marker and marker in normalized)
    if marker_hits > 0:
        return marker_hits
    if any(marker in normalized for marker in _UK_MARKERS):
        return 1
    return 0


def _materialize(record: dict[str, object]) -> dict[str, object]:
    return {
        "title": str(record["title"]),
        "url": str(record["url"]),
        "snippet": str(record["snippet"]),
        "authority": str(record["authority"]),
        "jurisdiction": str(record["jurisdiction"]),
        "publication_date": str(record["publication_date"]),
        "effective_date": None,
        "version": str(record["version"]),
    }


async def search_uk_legislation(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    """Return direct official UK legislation pages for UK policy queries."""
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    normalized_query = query.strip().lower()
    if not any(marker in normalized_query for marker in _UK_MARKERS):
        return []

    ranked = sorted(
        (
            (score, record)
            for record in _CATALOG
            if (score := _record_score(normalized_query, record)) > 0
        ),
        key=lambda item: (item[0], str(item[1]["publication_date"]), str(item[1]["url"])),
        reverse=True,
    )
    results = [_materialize(record) for _, record in ranked[: max(1, max_results)]]
    _CACHE.set(key, results, ttl_seconds=config.search_cache_ttl_seconds)
    return results
