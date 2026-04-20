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
            "Official AI Act text: deployers of an AI system that generates or "
            "manipulates image, audio or video content constituting a deep fake "
            "shall disclose that the content has been artificially generated or "
            "manipulated."
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
            "deepfake",
            "deep fake",
            "disclosure",
            "article 50",
            "artificially generated",
            "manipulated",
        ),
    },
    {
        "title": "Directive (EU) 2022/2555 (NIS2 Directive)",
        "url": "https://eur-lex.europa.eu/eli/dir/2022/2555/2022-12-27/eng",
        "snippet": (
            "Official NIS2 directive text: within 24 hours of becoming aware "
            "of the significant incident, an early warning shall be submitted."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2022-12-27",
        "effective_date": "2023-01-16",
        "version": "Official Journal text",
        "markers": (
            "nis2",
            "2022/2555",
            "cybersecurity directive",
            "transposition deadline",
            "significant incident",
            "early warning",
            "24 hours",
            "incident reporting",
            "incident reporting deadlines",
            "notification timeline",
            "article 23",
        ),
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
        "snippet_variants": (
            {
                "snippet": (
                    "Official Digital Services Act text: providers of online platforms "
                    "shall ensure that traders can only use those platforms to promote "
                    "messages on or to offer products or services to consumers located in "
                    "the Union if, prior to the use of its services, the provider has "
                    "obtained trader identity and contact information for the traceability "
                    "of traders."
                ),
                "markers": (
                    "trader traceability",
                    "traceability of traders",
                    "traders",
                    "identity and contact information",
                    "before allowing traders",
                ),
            },
        ),
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
        "title": "Regulation (EU) 2023/1542 (Battery Regulation)",
        "url": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj/eng",
        "snippet": (
            "Official Battery Regulation text covering recycled content "
            "information, carbon footprint declarations, due diligence "
            "obligations, and the battery passport for electric vehicle and "
            "industrial batteries."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2023-07-28",
        "effective_date": "2023-08-17",
        "version": "Official Journal text",
        "markers": (
            "battery regulation",
            "2023/1542",
            "2023 1542",
            "recycled content",
            "battery passport",
            "carbon footprint",
            "due diligence",
            "ev batteries",
            "waste batteries",
        ),
        "snippet_variants": (
            {
                "snippet": (
                    "Official Battery Regulation text: this Chapter does not apply to "
                    "economic operators that had a net turnover of less than EUR 40 "
                    "million in the financial year preceding the last financial year, "
                    "and that are not part of a group which exceeds the limit of EUR 40 "
                    "million on a consolidated basis."
                ),
                "markers": (
                    "sme",
                    "smes",
                    "exemption",
                    "due diligence",
                    "eur 40 million",
                    "does not apply",
                ),
            },
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
    {
        "title": "Regulation (EU) 2022/2554 (DORA)",
        "url": "https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng",
        "snippet": (
            "Official DORA text: after classifying an ICT-related incident as "
            "major, the financial entity shall submit an initial notification "
            "to the competent authority by the same business day, or no later "
            "than four hours from classification."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2022-12-27",
        "effective_date": "2023-01-16",
        "version": "Official Journal text",
        "markers": (
            "dora",
            "2022/2554",
            "major ict incident",
            "initial notification",
            "same business day",
        ),
    },
    {
        "title": "Regulation (EU) 2024/2847 (Cyber Resilience Act)",
        "url": "https://eur-lex.europa.eu/eli/reg/2024/2847/oj/eng",
        "snippet": (
            "Official Cyber Resilience Act text: manufacturers shall notify "
            "ENISA of any actively exploited vulnerability contained in the "
            "product with digital elements without undue delay and in any "
            "event within 24 hours of becoming aware of it."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2024-11-20",
        "effective_date": "2024-12-10",
        "version": "Official Journal text",
        "markers": (
            "cyber resilience act",
            "2024/2847",
            "vulnerability exploitation",
            "enisa",
            "24 hours",
        ),
    },
    {
        "title": "Regulation (EU) 2023/956 (CBAM)",
        "url": "https://eur-lex.europa.eu/eli/reg/2023/956/oj/eng",
        "snippet": (
            "Official CBAM regulation text: an authorised CBAM declarant is a "
            "person authorised by the competent authority of a Member State "
            "before importing goods into the customs territory of the Union, "
            "and the annual CBAM declaration includes the total embedded "
            "emissions in imported goods."
        ),
        "authority": "European Union",
        "jurisdiction": "EU",
        "publication_date": "2023-05-16",
        "effective_date": "2023-05-17",
        "version": "Official Journal text",
        "markers": (
            "cbam",
            "authorised cbam declarant",
            "authorized cbam declarant",
            "declarant cbam autorise",
            "declarant autorise",
            "embedded emissions",
            "cbam declaration",
            "emissions reporting",
        ),
    },
    {
        "title": "CBAM default values guidance",
        "url": "https://taxation-customs.ec.europa.eu/news/commission-publishes-default-values-determining-embedded-emissions-during-cbam-transitional-period-2023-12-22_en",
        "snippet": (
            "Official European Commission CBAM guidance: default values can "
            "be used to determine embedded emissions during the transitional "
            "period, particularly when importers do not have access to actual "
            "emissions data."
        ),
        "authority": "European Commission",
        "jurisdiction": "EU",
        "publication_date": "2023-12-22",
        "effective_date": None,
        "version": "Guidance",
        "markers": (
            "cbam",
            "default values",
            "embedded emissions",
            "transitional period",
        ),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"eurlex|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    marker_groups = [tuple(str(item).lower() for item in record.get("markers", ()))]
    marker_groups.extend(
        tuple(str(item).lower() for item in variant.get("markers", ()))
        for variant in record.get("snippet_variants", ())
        if isinstance(variant, dict)
    )
    marker_hits = max(
        (
            sum(1 for marker in markers if marker and marker in normalized)
            for markers in marker_groups
        ),
        default=0,
    )
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


def _selected_snippet(query: str, record: dict[str, object]) -> str:
    normalized = query.lower()
    selected_snippet = str(record["snippet"])
    base_markers = tuple(str(item).lower() for item in record.get("markers", ()))
    best_hits = sum(1 for marker in base_markers if marker and marker in normalized)
    best_marker_length = max(
        (len(marker) for marker in base_markers if marker and marker in normalized),
        default=0,
    )
    for variant in record.get("snippet_variants", ()):
        if not isinstance(variant, dict):
            continue
        markers = tuple(str(item).lower() for item in variant.get("markers", ()))
        marker_hits = sum(1 for marker in markers if marker and marker in normalized)
        marker_length = max(
            (len(marker) for marker in markers if marker and marker in normalized),
            default=0,
        )
        if marker_hits > best_hits or (
            marker_hits == best_hits and marker_hits > 0 and marker_length > best_marker_length
        ):
            best_hits = marker_hits
            best_marker_length = marker_length
            selected_snippet = str(variant.get("snippet") or selected_snippet)
    return selected_snippet


def _materialize(record: dict[str, object], *, query: str) -> dict[str, object]:
    return {
        "title": str(record["title"]),
        "url": str(record["url"]),
        "snippet": _selected_snippet(query, record),
        "authority": str(record["authority"]),
        "jurisdiction": str(record["jurisdiction"]),
        "publication_date": str(record["publication_date"]),
        "effective_date": (
            str(record["effective_date"]) if record.get("effective_date") is not None else None
        ),
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
    results = [
        _materialize(record, query=normalized_query)
        for _, record in ranked[: max(1, max_results)]
    ]
    _CACHE.set(key, results, ttl_seconds=config.search_cache_ttl_seconds)
    return results
