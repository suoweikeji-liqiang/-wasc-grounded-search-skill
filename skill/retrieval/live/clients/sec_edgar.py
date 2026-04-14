"""Official SEC EDGAR search client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.clients import http as http_client

_SEARCH_ENDPOINT = "https://efts.sec.gov/LATEST/search-index"
_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_FORM_MARKERS: tuple[tuple[str, str], ...] = (
    ("10-k", "10-K"),
    ("10k", "10-K"),
    ("10-q", "10-Q"),
    ("10q", "10-Q"),
    ("8-k", "8-K"),
    ("8k", "8-K"),
    ("20-f", "20-F"),
    ("20f", "20-F"),
    ("6-k", "6-K"),
    ("6k", "6-K"),
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"sec|{query.strip().lower()}|{max(1, max_results)}"


def _detect_form(query: str) -> str | None:
    normalized = query.lower()
    for marker, form in _FORM_MARKERS:
        if marker in normalized:
            return form
    return None


def _sec_result_url(source: dict[str, object], raw_id: str) -> str | None:
    cik_values = source.get("ciks")
    adsh = str(source.get("adsh") or "").strip()
    if not isinstance(cik_values, list) or not cik_values or not adsh:
        return None
    cik = str(cik_values[0]).strip().lstrip("0") or "0"
    compact_adsh = adsh.replace("-", "")
    filename = raw_id.split(":", 1)[1] if ":" in raw_id else ""
    if not filename:
        return None
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{compact_adsh}/{filename}"


async def search_sec_filings(
    *,
    query: str,
    max_results: int = 3,
) -> list[dict[str, object]]:
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    params = {
        "q": query,
        "category": "custom",
        "from": "0",
        "size": str(max(1, max_results)),
    }
    detected_form = _detect_form(query)
    if detected_form is not None:
        params["forms"] = detected_form

    payload = await http_client.fetch_json(
        url=_SEARCH_ENDPOINT,
        params=params,
        headers={"User-Agent": "WASC-clean/1.0 (public retrieval client)"},
        timeout=2.5,
    )
    if not isinstance(payload, dict):
        return []
    hits_container = payload.get("hits")
    if not isinstance(hits_container, dict):
        return []
    hits = hits_container.get("hits")
    if not isinstance(hits, list):
        return []

    parsed: list[dict[str, object]] = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        source = item.get("_source")
        raw_id = str(item.get("_id") or "")
        if not isinstance(source, dict):
            continue
        url = _sec_result_url(source, raw_id)
        if not url:
            continue
        display_names = source.get("display_names")
        company_name = (
            str(display_names[0]).split("(CIK", 1)[0].strip()
            if isinstance(display_names, list) and display_names
            else "SEC registrant"
        )
        form = str(source.get("form") or source.get("file_type") or "filing").strip()
        file_date = str(source.get("file_date") or "").strip()
        title = f"{company_name} Form {form} filing"
        snippet_parts = [
            "Official SEC filing",
            form,
            f"filed {file_date}" if file_date else "",
            str(source.get("file_description") or "").strip(),
        ]
        parsed.append(
            {
                "title": title,
                "url": url,
                "snippet": " ".join(part for part in snippet_parts if part).strip(),
                "credibility_tier": "company_official",
            }
        )

    clipped = parsed[: max(1, max_results)]
    _CACHE.set(key, clipped, ttl_seconds=config.search_cache_ttl_seconds)
    return clipped
