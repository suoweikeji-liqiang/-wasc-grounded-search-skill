"""Direct official FinCEN policy source client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_FINCEN_MARKERS: tuple[str, ...] = (
    "fincen",
    "boi",
    "beneficial ownership",
    "corporate transparency act",
)
_CATALOG: tuple[dict[str, object], ...] = (
    {
        "title": "Beneficial Ownership Information Reporting",
        "url": "https://www.fincen.gov/boi",
        "snippet": (
            "Official FinCEN BOI reporting portal and guidance under the "
            "Corporate Transparency Act."
        ),
        "authority": "Financial Crimes Enforcement Network",
        "jurisdiction": "US",
        "publication_date": "2023-09-29",
        "effective_date": "2024-01-01",
        "version": "BOI guidance",
        "markers": ("boi", "beneficial ownership", "corporate transparency act"),
    },
    {
        "title": "Beneficial Ownership Information Access and Safeguards Rule",
        "url": "https://www.federalregister.gov/documents/2023/12/22/2023-27973/beneficial-ownership-information-access-and-safeguards",
        "snippet": "Official Federal Register publication for BOI access and safeguards.",
        "authority": "Financial Crimes Enforcement Network",
        "jurisdiction": "US",
        "publication_date": "2023-12-22",
        "effective_date": "2024-02-20",
        "version": "Final rule",
        "markers": ("access rule", "safeguards rule", "federal register boi"),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"fincen|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    markers = tuple(str(item).lower() for item in record.get("markers", ()))
    marker_hits = sum(1 for marker in markers if marker and marker in normalized)
    if marker_hits > 0:
        return marker_hits
    return 1 if any(marker in normalized for marker in _FINCEN_MARKERS) else 0


def _materialize(record: dict[str, object]) -> dict[str, object]:
    return {
        "title": str(record["title"]),
        "url": str(record["url"]),
        "snippet": str(record["snippet"]),
        "authority": str(record["authority"]),
        "jurisdiction": str(record["jurisdiction"]),
        "publication_date": str(record["publication_date"]),
        "effective_date": str(record["effective_date"]),
        "version": str(record["version"]),
    }


async def search_fincen_policy(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    """Return direct official FinCEN policy pages for BOI-style queries."""
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    normalized_query = query.strip().lower()
    if not any(marker in normalized_query for marker in _FINCEN_MARKERS):
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
