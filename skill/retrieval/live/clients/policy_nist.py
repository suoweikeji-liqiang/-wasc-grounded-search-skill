"""Direct official NIST policy source client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_NIST_MARKERS: tuple[str, ...] = (
    "nist",
    "fips",
    "post-quantum",
    "post quantum",
    "ml-kem",
    "ml-dsa",
    "slh-dsa",
)
_CATALOG: tuple[dict[str, object], ...] = (
    {
        "title": "FIPS 203, Module-Lattice-Based Key-Encapsulation Mechanism Standard",
        "url": "https://csrc.nist.gov/pubs/fips/203/final",
        "snippet": "Official NIST FIPS 203 final publication page.",
        "authority": "National Institute of Standards and Technology",
        "jurisdiction": "US",
        "publication_date": "2024-08-13",
        "effective_date": None,
        "version": "Final",
        "markers": ("fips 203", "203", "ml-kem", "key encapsulation"),
    },
    {
        "title": "FIPS 204, Module-Lattice-Based Digital Signature Standard",
        "url": "https://csrc.nist.gov/pubs/fips/204/final",
        "snippet": "Official NIST FIPS 204 final publication page.",
        "authority": "National Institute of Standards and Technology",
        "jurisdiction": "US",
        "publication_date": "2024-08-13",
        "effective_date": None,
        "version": "Final",
        "markers": ("fips 204", "204", "ml-dsa", "digital signature"),
    },
    {
        "title": "FIPS 205, Stateless Hash-Based Digital Signature Standard",
        "url": "https://csrc.nist.gov/pubs/fips/205/final",
        "snippet": "Official NIST FIPS 205 final publication page.",
        "authority": "National Institute of Standards and Technology",
        "jurisdiction": "US",
        "publication_date": "2024-08-13",
        "effective_date": None,
        "version": "Final",
        "markers": ("fips 205", "205", "slh-dsa", "hash-based digital signature"),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"nist|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    markers = tuple(str(item).lower() for item in record.get("markers", ()))
    marker_hits = sum(1 for marker in markers if marker and marker in normalized)
    if marker_hits > 0:
        return marker_hits
    if any(marker in normalized for marker in _NIST_MARKERS):
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


async def search_nist_publications(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    """Return direct official NIST policy pages for standards-oriented queries."""
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    normalized_query = query.strip().lower()
    if not any(marker in normalized_query for marker in _NIST_MARKERS):
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
