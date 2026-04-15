"""Official SEC EDGAR search client."""

from __future__ import annotations

import re

from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.clients import http as http_client

_SEARCH_ENDPOINT = "https://efts.sec.gov/LATEST/search-index"
_SUBMISSIONS_ENDPOINT = "https://data.sec.gov/submissions/CIK{cik}.json"
_COMPANY_TICKERS_ENDPOINT = "https://www.sec.gov/files/company_tickers.json"
_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_SUBMISSIONS_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_COMPANY_TICKERS_CACHE: TTLCache[tuple[dict[str, object], ...]] = TTLCache(max_entries=1)
_SEC_CONTACT_USER_AGENT = "WASC-clean/1.0 (contact: wasc-clean@example.com)"
_COMPANY_TICKERS_CACHE_KEY = "sec-company-tickers"
_COMPANY_TICKERS_CACHE_TTL_SECONDS = 86_400
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
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_CIK_DIGITS_RE = re.compile(r"\d+")
_TICKER_TOKEN_RE = re.compile(r"[a-z0-9]{2,6}")
_LEGAL_SUFFIX_TOKENS: frozenset[str] = frozenset(
    {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "companies",
        "ltd",
        "limited",
        "llc",
        "lp",
        "plc",
        "sa",
        "ag",
        "nv",
        "se",
        "spa",
        "de",
    }
)
_TRAILING_DESCRIPTOR_TOKENS: frozenset[str] = frozenset(
    {
        "holding",
        "holdings",
        "group",
        "platform",
        "platforms",
    }
)
_KNOWN_COMPANIES: tuple[dict[str, object], ...] = (
    {
        "aliases": ("microsoft",),
        "cik": "0000789019",
    },
    {
        "aliases": ("boeing",),
        "cik": "0000012927",
    },
    {
        "aliases": ("jpmorgan chase", "jpmorgan"),
        "cik": "0000019617",
    },
    {
        "aliases": ("ford", "ford motor"),
        "cik": "0000037996",
    },
    {
        "aliases": ("exxonmobil", "exxon mobil"),
        "cik": "0000034088",
    },
    {
        "aliases": ("nvidia",),
        "cik": "0001045810",
    },
    {
        "aliases": ("rivian",),
        "cik": "0001874178",
    },
    {
        "aliases": ("tsmc", "taiwan semiconductor", "taiwan semiconductor manufacturing"),
        "cik": "0001046179",
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"sec|{query.strip().lower()}|{max(1, max_results)}"


def _submissions_cache_key(query: str, *, max_results: int) -> str:
    return f"sec-submissions|{query.strip().lower()}|{max(1, max_results)}"


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


def _marker_in_query(normalized_query: str, marker: str) -> bool:
    return re.search(
        rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
        normalized_query,
    ) is not None


def _detect_known_company_cik(query: str) -> str | None:
    normalized = normalize_query_text(query)
    best_match: tuple[int, str] | None = None
    for company in _KNOWN_COMPANIES:
        cik = str(company["cik"])
        for alias in company["aliases"]:
            alias_text = str(alias)
            if not _marker_in_query(normalized, alias_text):
                continue
            candidate = (len(alias_text), cik)
            if best_match is None or candidate > best_match:
                best_match = candidate
    return None if best_match is None else best_match[1]


def has_known_company_submission_target(query: str) -> bool:
    return _detect_known_company_cik(query) is not None


def _ascii_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in query_tokens(normalize_query_text(text))
        if token.isascii()
    )


def _strip_trailing_tokens(
    tokens: tuple[str, ...],
    removable: frozenset[str],
) -> tuple[str, ...]:
    trimmed = list(tokens)
    while trimmed and trimmed[-1] in removable:
        trimmed.pop()
    return tuple(trimmed)


def _normalize_cik(value: object) -> str | None:
    digits_match = _CIK_DIGITS_RE.findall(str(value or ""))
    digits = "".join(digits_match).strip()
    if not digits:
        return None
    return digits.zfill(10)


def _company_alias_entries(
    *,
    title: str,
    ticker: str,
) -> tuple[dict[str, object], ...]:
    title_tokens = _ascii_tokens(title)
    core_tokens = _strip_trailing_tokens(title_tokens, _LEGAL_SUFFIX_TOKENS) or title_tokens
    alias_entries: list[dict[str, object]] = []
    seen_aliases: set[str] = set()

    def _add_alias(alias_text: str, *, priority: int) -> None:
        normalized_alias = normalize_query_text(alias_text)
        if not normalized_alias or normalized_alias in seen_aliases:
            return
        seen_aliases.add(normalized_alias)
        alias_entries.append(
            {
                "alias": normalized_alias,
                "priority": priority,
                "token_count": len(normalized_alias.split()),
            }
        )

    if core_tokens:
        _add_alias(" ".join(core_tokens), priority=4)
        for prefix_length in range(len(core_tokens) - 1, 1, -1):
            _add_alias(" ".join(core_tokens[:prefix_length]), priority=3)

        trimmed_tokens = core_tokens
        while len(trimmed_tokens) >= 2 and trimmed_tokens[-1] in _TRAILING_DESCRIPTOR_TOKENS:
            trimmed_tokens = trimmed_tokens[:-1]
            _add_alias(" ".join(trimmed_tokens), priority=3)
            if len(trimmed_tokens) == 1 and len(trimmed_tokens[0]) >= 4:
                _add_alias(trimmed_tokens[0], priority=2)

        acronym = "".join(token[0] for token in core_tokens if token)
        if 2 <= len(acronym) <= 5:
            _add_alias(acronym, priority=2)

    normalized_ticker = normalize_query_text(ticker)
    if _TICKER_TOKEN_RE.fullmatch(normalized_ticker or ""):
        _add_alias(normalized_ticker, priority=1)

    return tuple(alias_entries)


def _parse_company_ticker_payload(payload: object) -> tuple[dict[str, object], ...]:
    rows: object
    if isinstance(payload, dict):
        rows = payload.values()
    elif isinstance(payload, list):
        rows = payload
    else:
        return ()

    parsed: list[dict[str, object]] = []
    seen_entries: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cik = _normalize_cik(row.get("cik_str"))
        title = str(row.get("title") or "").strip()
        ticker = str(row.get("ticker") or "").strip()
        if cik is None or not title:
            continue
        for alias_entry in _company_alias_entries(title=title, ticker=ticker):
            alias = str(alias_entry["alias"])
            dedupe_key = (alias, cik)
            if dedupe_key in seen_entries:
                continue
            seen_entries.add(dedupe_key)
            parsed.append(
                {
                    "alias": alias,
                    "priority": int(alias_entry["priority"]),
                    "token_count": int(alias_entry["token_count"]),
                    "cik": cik,
                }
            )
    return tuple(parsed)


async def _load_company_ticker_directory() -> tuple[dict[str, object], ...]:
    cached = _COMPANY_TICKERS_CACHE.get(_COMPANY_TICKERS_CACHE_KEY)
    if cached is not None:
        return cached

    payload = await http_client.fetch_json(
        url=_COMPANY_TICKERS_ENDPOINT,
        headers={"User-Agent": _SEC_CONTACT_USER_AGENT},
        timeout=4.0,
    )
    parsed = _parse_company_ticker_payload(payload)
    _COMPANY_TICKERS_CACHE.set(
        _COMPANY_TICKERS_CACHE_KEY,
        parsed,
        ttl_seconds=_COMPANY_TICKERS_CACHE_TTL_SECONDS,
    )
    return parsed


async def _detect_company_cik(query: str) -> str | None:
    known_cik = _detect_known_company_cik(query)
    if known_cik is not None:
        return known_cik

    normalized = normalize_query_text(query)
    best_match: tuple[int, int, int, str] | None = None
    for candidate in await _load_company_ticker_directory():
        alias = str(candidate["alias"])
        if not _marker_in_query(normalized, alias):
            continue
        match_key = (
            int(candidate["priority"]),
            int(candidate["token_count"]),
            len(alias),
            str(candidate["cik"]),
        )
        if best_match is None or match_key > best_match:
            best_match = match_key
    return None if best_match is None else best_match[3]


async def has_company_submission_target(query: str) -> bool:
    return await _detect_company_cik(query) is not None


def _query_years(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_YEAR_RE.findall(query)))


def _preferred_forms(query: str) -> tuple[str, ...]:
    normalized = normalize_query_text(query)
    detected_form = _detect_form(query)
    if detected_form is not None:
        if detected_form == "10-K":
            return ("10-K", "10-K/A")
        if detected_form == "10-Q":
            return ("10-Q", "10-Q/A")
        if detected_form == "8-K":
            return ("8-K", "8-K/A")
        if detected_form == "20-F":
            return ("20-F", "20-F/A")
        if detected_form == "6-K":
            return ("6-K",)
        return (detected_form,)
    if "annual report" in normalized:
        return ("10-K", "20-F", "10-K/A", "20-F/A")
    if "quarterly report" in normalized:
        return ("10-Q", "10-Q/A", "6-K")
    if "earnings" in normalized or "guidance" in normalized:
        return ("8-K", "6-K", "10-Q", "10-K", "20-F")
    return ("10-K", "20-F", "8-K", "6-K", "10-Q")


def _filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    compact_cik = cik.lstrip("0") or "0"
    compact_accession = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{compact_cik}/{compact_accession}/{primary_document}"
    )


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


async def search_sec_company_submissions(
    *,
    query: str,
    max_results: int = 3,
) -> list[dict[str, object]]:
    config = LiveRetrievalConfig.from_env()
    key = _submissions_cache_key(query, max_results=max_results)
    cached = _SUBMISSIONS_CACHE.get(key)
    if cached is not None:
        return cached

    cik = await _detect_company_cik(query)
    if cik is None:
        return []

    payload = await http_client.fetch_json(
        url=_SUBMISSIONS_ENDPOINT.format(cik=cik),
        headers={"User-Agent": _SEC_CONTACT_USER_AGENT},
        timeout=4.0,
    )
    if not isinstance(payload, dict):
        return []

    filings = payload.get("filings")
    if not isinstance(filings, dict):
        return []
    recent = filings.get("recent")
    if not isinstance(recent, dict):
        return []

    forms = recent.get("form")
    accession_numbers = recent.get("accessionNumber")
    primary_documents = recent.get("primaryDocument")
    filing_dates = recent.get("filingDate")
    report_dates = recent.get("reportDate")
    if not all(isinstance(field, list) for field in (forms, accession_numbers, primary_documents, filing_dates)):
        return []

    query_year_set = set(_query_years(query))
    preferred_forms = _preferred_forms(query)
    form_priority = {form: index for index, form in enumerate(preferred_forms)}
    parsed: list[dict[str, object]] = []
    count = min(
        len(forms),
        len(accession_numbers),
        len(primary_documents),
        len(filing_dates),
        len(report_dates) if isinstance(report_dates, list) else len(forms),
    )
    company_name = str(payload.get("name") or "SEC registrant").replace(" / DE", "")

    for index in range(count):
        form = str(forms[index] or "").strip()
        accession_number = str(accession_numbers[index] or "").strip()
        primary_document = str(primary_documents[index] or "").strip()
        filing_date = str(filing_dates[index] or "").strip()
        report_date = (
            str(report_dates[index] or "").strip()
            if isinstance(report_dates, list) and index < len(report_dates)
            else ""
        )
        if form not in form_priority or not accession_number or not primary_document:
            continue
        report_year_match = int(bool(query_year_set & {report_date[:4]}))
        filing_year_match = int(bool(query_year_set & {filing_date[:4]}))
        parsed.append(
            {
                "title": f"{company_name} Form {form} filing",
                "url": _filing_url(cik, accession_number, primary_document),
                "snippet": " ".join(
                    part
                    for part in (
                        "Official SEC filing",
                        form,
                        f"filed {filing_date}" if filing_date else "",
                        f"report period {report_date}" if report_date else "",
                    )
                    if part
                ),
                "credibility_tier": "company_official",
                "_priority": form_priority[form],
                "_report_year_match": report_year_match,
                "_filing_year_match": filing_year_match,
                "_report_date": report_date,
                "_filing_date": filing_date,
            }
        )

    parsed.sort(
        key=lambda item: (
            int(item["_report_year_match"]),
            int(item["_filing_year_match"]),
            -int(item["_priority"]),
            str(item["_report_date"]),
            str(item["_filing_date"]),
            str(item["url"]),
        ),
        reverse=True,
    )
    clipped = [
        {
            "title": str(item["title"]),
            "url": str(item["url"]),
            "snippet": str(item["snippet"]),
            "credibility_tier": str(item["credibility_tier"]),
        }
        for item in parsed[: max(1, max_results)]
    ]
    _SUBMISSIONS_CACHE.set(key, clipped, ttl_seconds=config.search_cache_ttl_seconds)
    return clipped
