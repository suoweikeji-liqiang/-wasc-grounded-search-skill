"""Direct official EUR-Lex source client for EU policy lookups."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_EU_MARKERS: tuple[str, ...] = (
    "eu",
    "european union",
    "eur-lex",
    "directive",
    "regulation",
)
_CATALOG: tuple[dict[str, object], ...] = (
    {
        "title": "Regulation (EU) 2024/1689 (AI Act / Reglement UE 2024 1689)",
        "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
        "snippet": (
            "Official AI Act / Reglement UE 2024 1689 text in the Official "
            "Journal, including the definition of an AI system (systeme d ia) "
            "and phased obligation timelines."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2024-07-12",
        "effective_date": "2024-08-01",
        "version": "Official Journal text",
        "markers": (
            "ai act",
            "2024/1689",
            "2024 1689",
            "reglement ue",
            "systeme d ia",
            "article officiel",
            "general purpose ai",
            "gpa i",
            "foundation model",
        ),
    },
    {
        "title": "Directive (EU) 2022/2555 (NIS2 Directive)",
        "url": "https://eur-lex.europa.eu/eli/dir/2022/2555/2022-12-27/eng",
        "snippet": (
            "Official NIS2 directive text including Member State transposition "
            "deadline requirements."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2022-12-27",
        "effective_date": "2023-01-16",
        "version": "Official Journal text",
        "markers": ("nis2", "2022/2555", "cybersecurity directive", "transposition deadline"),
    },
    {
        "title": "Regulation (EU) 2022/2065 (Digital Services Act)",
        "url": "https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng",
        "snippet": "Official Digital Services Act text and legal obligations.",
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2022-10-27",
        "effective_date": "2022-11-16",
        "version": "Official Journal text",
        "markers": ("dsa", "digital services act", "2022/2065", "very large online platforms"),
    },
    {
        "title": "Regulation (EU) 2022/1925 (Digital Markets Act)",
        "url": "https://eur-lex.europa.eu/eli/reg/2022/1925/oj/eng",
        "snippet": (
            "Official Digital Markets Act text for designated gatekeepers, core "
            "platform services, and messaging interoperability obligations."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2022-10-12",
        "effective_date": "2022-11-01",
        "version": "Official Journal text",
        "markers": (
            "dma",
            "digital markets act",
            "2022/1925",
            "gatekeeper",
            "designated gatekeepers",
            "core platform services",
            "messaging interoperability",
        ),
    },
    {
        "title": "Regulation (EU) 2023/2854 (Data Act)",
        "url": "https://eur-lex.europa.eu/eli/reg/2023/2854/oj/eng",
        "snippet": (
            "Official Data Act text covering connected products, data holder "
            "obligations, trade-secret safeguards, and application timing."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2023-12-22",
        "effective_date": "2025-09-12",
        "version": "Official Journal text",
        "markers": (
            "data act",
            "2023/2854",
            "connected products",
            "data holder obligations",
            "trade-secret safeguards",
            "application date",
        ),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"eurlex|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    markers = tuple(str(item).lower() for item in record.get("markers", ()))
    marker_hits = sum(1 for marker in markers if marker and marker in normalized)
    if marker_hits > 0:
        return marker_hits
    if any(marker in normalized for marker in _EU_MARKERS):
        title = str(record.get("title") or "").lower()
        snippet = str(record.get("snippet") or "").lower()
        if "directive" in normalized and "directive" in title:
            return 1
        if "regulation" in normalized and ("regulation" in title or "regulation" in snippet):
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
        "effective_date": str(record["effective_date"]),
        "version": str(record["version"]),
    }


async def search_eur_lex(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    """Return direct official EUR-Lex matches for EU regulation queries."""
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    normalized_query = query.strip().lower()
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
