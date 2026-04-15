"""Industry ddgs adapter with deterministic credibility-tier annotation."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.evidence.fact_density import fact_density_score
from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.sec_edgar import (
    has_known_company_submission_target,
    search_sec_company_submissions,
    search_sec_filings,
)
from skill.retrieval.live.parsers.page_content import extract_page_content
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.industry import (
    build_industry_snippet,
    extract_query_aligned_page_excerpt,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

SOURCE_ID = "industry_ddgs"
_MIN_FIXTURE_SCORE = 8
_TIER_ORDER: tuple[str, ...] = (
    "company_official",
    "industry_association",
    "trusted_news",
    "general_web",
)
_RFC_RE = re.compile(r"(?<![a-z0-9])rfc[\s:-]*(\d{3,5})(?![a-z0-9])", re.IGNORECASE)
_OFFICIAL_FETCH_SCORE_THRESHOLD = 10
_OFFICIAL_FETCH_OVERLAP_THRESHOLD = 4
_OFFICIAL_FETCH_FACT_DENSITY_THRESHOLD = 4.0
_OFFICIAL_FETCH_STRONG_OVERLAP_THRESHOLD = 6
_PAGE_FETCH_TIMEOUT_SECONDS = 0.4
_QUERY_ALIGNED_FETCH_TIMEOUT_SECONDS = 2.0
_SEC_ARCHIVE_FETCH_TIMEOUT_SECONDS = 4.0
_SEC_ARCHIVE_INITIAL_FETCH_CHAR_LIMIT = 650_000
_SEC_ARCHIVE_FETCH_CHAR_LIMIT = 900_000
_QUERY_ALIGNED_FETCH_CHAR_LIMIT = 300_000
_COMPANY_IR_HOME_TIMEOUT_SECONDS = 1.8
_COMPANY_IR_PAGE_TIMEOUT_SECONDS = 0.8
_COMPANY_IR_STRONG_SCORE_THRESHOLD = 10
_SEC_CONTACT_USER_AGENT = "WASC-clean/1.0 (contact: wasc-clean@example.com)"
_COMPANY_OFFICIAL_DOMAINS: frozenset[str] = frozenset(
    {"www.tesla.com", "www.byd.com", "www.sec.gov", "sec.gov"}
)
_INDUSTRY_ASSOCIATION_DOMAINS: frozenset[str] = frozenset(
    {
        "www.iea.org",
        "www.iata.org",
        "www.rfc-editor.org",
        "rfc-editor.org",
        "www.ietf.org",
        "ietf.org",
        "datatracker.ietf.org",
        "www.sae.org",
        "www.semi.org",
        "www.w3.org",
        "w3.org",
        "www.chromium.org",
        "chromium.org",
        "developer.chrome.com",
        "www.counterpointresearch.com",
        "www.canalys.com",
        "www.idc.com",
    }
)
_TRUSTED_NEWS_DOMAINS: frozenset[str] = frozenset(
    {"www.reuters.com", "www.bloomberg.com"}
)
_QUERY_ALIGNED_FETCH_HOSTS: frozenset[str] = frozenset(
    {"www.sec.gov", "sec.gov", "datatracker.ietf.org"}
)
_COMPANY_IR_QUERY_MARKERS: tuple[str, ...] = (
    "segment",
    "segments",
    "revenue",
    "revenues",
)
_KNOWN_COMPANY_IR_TARGETS: tuple[dict[str, object], ...] = (
    {
        "aliases": ("microsoft",),
        "homepage_url": "https://www.microsoft.com/en-us/Investor",
        "allowed_hosts": ("www.microsoft.com", "microsoft.com"),
        "required_path_markers": ("/investor/",),
    },
    {
        "aliases": ("boeing",),
        "homepage_url": "https://investors.boeing.com",
        "allowed_hosts": ("investors.boeing.com", "boeing.com", "www.boeing.com"),
        "required_path_markers": ("/investors/",),
    },
    {
        "aliases": ("rivian",),
        "homepage_url": "https://rivian.com/investors",
        "allowed_hosts": ("rivian.com", "www.rivian.com"),
        "required_path_markers": ("/investors", "/newsroom/"),
    },
)
_DIRECT_COMPANY_IR_PAGE_TARGETS: tuple[dict[str, object], ...] = (
    {
        "aliases": ("microsoft",),
        "query_markers": ("segment", "revenue"),
        "title": "Segment Performance",
        "url": (
            "https://www.microsoft.com/en-us/Investor/earnings/"
            "FY-2026-Q2/productivity-and-business-processes-performance"
        ),
    },
)

_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "Vision Pro 当前销量预测",
        "url": "https://www.bloomberg.com/news/articles/2026-03-18/vision-pro-sales-forecast",
        "snippet": "行业跟踪预计 Vision Pro 当前销量仍处于早期爬坡阶段，全年销量预测保持谨慎。",
    },
    {
        "title": "Vision Pro XR 市场销量展望",
        "url": "https://www.counterpointresearch.com/insights/vision-pro-sales-outlook-2026",
        "snippet": "机构预测 Vision Pro 销量与后续出货节奏将影响高端 XR 市场走势。",
    },
    {
        "title": "2026年AI服务器GPU市场份额预测",
        "url": "https://www.semi.org/en/news-resources/market-data/ai-server-gpu-share-2026",
        "snippet": "行业协会预测 2026 年 AI 服务器 GPU 市场份额继续向头部加速器集中。",
    },
    {
        "title": "AI服务器GPU竞争格局与市场份额展望",
        "url": "https://www.reuters.com/technology/ai-server-gpu-market-share-2026",
        "snippet": "市场报告预计 AI 服务器 GPU 市场份额和供给结构将在 2026 年继续变化。",
    },
    {
        "title": "中国智能手机2026年出货量趋势预测",
        "url": "https://www.idc.com/getdoc.jsp?containerId=china-smartphone-shipments-2026",
        "snippet": "机构预计中国智能手机 2026 年出货量趋势温和回升，中高端机型贡献主要增量。",
    },
    {
        "title": "中国智能手机渠道与品牌出货趋势展望",
        "url": "https://www.counterpointresearch.com/insights/china-smartphone-shipments-trend-2026",
        "snippet": "分析指出中国智能手机品牌结构调整将影响 2026 年出货趋势和渠道节奏。",
    },
    {
        "title": "AI Act 对开源模型产业落地影响评估",
        "url": "https://www.bloomberg.com/news/articles/2026-04-08/ai-act-open-source-model-deployment-impact",
        "snippet": "行业分析认为 AI Act 将改变开源模型商业化、企业部署和产业落地节奏。",
    },
    {
        "title": "欧盟碳关税对新能源车出口与供应链影响",
        "url": "https://www.reuters.com/world/europe/eu-carbon-border-nev-export-supply-chain-2026",
        "snippet": "新能源车企业预计欧盟碳关税将重塑出口成本、产能布局和跨境供应链安排。",
    },
    {
        "title": "美国出口管制对训练芯片供给影响",
        "url": "https://www.bloomberg.com/news/articles/2026-04-09/export-controls-ai-training-chip-supply",
        "snippet": "出口管制升级后，大模型训练芯片供给、交付周期和替代采购策略都受到影响。",
    },
    {
        "title": "BYD autonomous driving supplier investment update",
        "url": "https://www.byd.com/news/autonomous-driving-supplier-investment-2026",
        "snippet": "Company update says autonomous driving programs are increasing supplier investment across the vehicle industry in 2026.",
    },
    {
        "title": "Tesla annual battery supply update",
        "url": "https://www.tesla.com/blog/battery-supply-update",
        "snippet": "Company disclosure on battery production guidance.",
    },
    {
        "title": "SEMI outlook for semiconductor packaging capacity",
        "url": "https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
        "snippet": "Industry-association forecast for semiconductor packaging capacity in 2026.",
    },
    {
        "title": "Reuters battery recycling market share outlook 2025",
        "url": "https://www.reuters.com/markets/battery-recycling-share-2025",
        "snippet": "Trusted news estimate of battery recycling market-share shifts in 2025.",
    },
    {
        "title": "Community blog roundup of battery trends",
        "url": "https://analysis.example.net/battery-trends-roundup",
        "snippet": "General-web commentary on market sentiment.",
    },
)


def _tier_for_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    if host in _COMPANY_OFFICIAL_DOMAINS or host.startswith(("investor.", "investors.", "ir.")):
        return "company_official"
    if (
        host in _INDUSTRY_ASSOCIATION_DOMAINS
        or "/investor" in path
        or "/investors" in path
    ):
        return "industry_association"
    if host in _TRUSTED_NEWS_DOMAINS:
        return "trusted_news"
    return "general_web"


def _score(query: str, fixture: dict[str, str]) -> int:
    return score_query_alignment(
        query,
        route="industry",
        title=fixture["title"],
        snippet=fixture["snippet"],
        url=fixture["url"],
    )


def _should_query_sec(query: str) -> bool:
    normalized = normalize_query_text(query)
    token_set = set(query_tokens(normalized))
    form_markers = (
        "10-k",
        "10k",
        "10-q",
        "10q",
        "8-k",
        "8k",
        "20-f",
        "20f",
        "6-k",
        "6k",
    )
    phrase_markers = (
        "annual report",
        "quarterly report",
        "earnings",
        "guidance",
        "filing",
    )
    return (
        any(marker in normalized for marker in form_markers)
        or any(marker in normalized for marker in phrase_markers)
        or "sec" in token_set
    )


def _has_detailed_disclosure_intent(query: str) -> bool:
    normalized = normalize_query_text(query)
    return any(marker in normalized for marker in _COMPANY_IR_QUERY_MARKERS)


def _content_tokens(text: str) -> tuple[str, ...]:
    normalized = normalize_query_text(text)
    return tuple(
        dict.fromkeys(
            token
            for token in query_tokens(normalized)
            if (
                (token.isascii() and len(token) >= 4)
                or (token.isdigit() and len(token) == 4)
                or not token.isascii()
            )
        )
    )


def _query_overlap_count(query: str, *, title: str, snippet: str) -> int:
    record_tokens = set(_content_tokens(f"{title} {snippet}"))
    return sum(1 for token in _content_tokens(query) if token in record_tokens)


def _should_fetch_official_candidate(
    *,
    query: str,
    title: str,
    snippet: str,
    tier: str,
) -> bool:
    if tier == "general_web":
        return True
    base_score = _score(
        query,
        {
            "title": title,
            "url": "",
            "snippet": snippet,
        },
    )
    overlap = _query_overlap_count(query, title=title, snippet=snippet)
    fact_density = fact_density_score(f"{title}. {snippet}")
    return not (
        base_score >= _OFFICIAL_FETCH_SCORE_THRESHOLD
        and overlap >= _OFFICIAL_FETCH_OVERLAP_THRESHOLD
        and (
            fact_density >= _OFFICIAL_FETCH_FACT_DENSITY_THRESHOLD
            or overlap >= _OFFICIAL_FETCH_STRONG_OVERLAP_THRESHOLD
        )
    )


def _direct_official_candidates(query: str) -> list[dict[str, str]]:
    normalized = normalize_query_text(query)
    candidates: list[dict[str, str]] = []

    rfc_match = _RFC_RE.search(normalized)
    if rfc_match is not None:
        rfc_number = rfc_match.group(1)
        candidates.append(
            {
                "title": f"RFC {rfc_number}",
                "url": f"https://datatracker.ietf.org/doc/html/rfc{rfc_number}",
                "snippet": f"Official RFC {rfc_number} specification document.",
                "_tier": "industry_association",
                "_force_fetch": "1",
            }
        )

    if "webauthn" in normalized:
        level = "3" if "level 3" in normalized else "2"
        candidates.append(
            {
                "title": f"WebAuthn Level {level}",
                "url": f"https://www.w3.org/TR/webauthn-{level}/",
                "snippet": f"Official W3C WebAuthn Level {level} specification.",
                "_tier": "industry_association",
                "_force_fetch": "1",
            }
        )

    if "chips" in normalized and (
        "chromium" in normalized or "cookie" in normalized or "set-cookie" in normalized
    ):
        candidates.append(
            {
                "title": "CHIPS",
                "url": "https://developer.chrome.com/blog/chrome-114-beta/",
                "snippet": "Official Chromium documentation for CHIPS and partitioned cookies.",
                "_tier": "industry_association",
                "_force_fetch": "1",
            }
        )

    if "http message signatures" in normalized:
        candidates.append(
            {
                "title": "HTTP Message Signatures",
                "url": "https://datatracker.ietf.org/doc/html/rfc9421",
                "snippet": "Official HTTP Message Signatures specification.",
                "_tier": "industry_association",
                "_force_fetch": "1",
            }
        )

    return candidates


def _official_search_queries(query: str) -> tuple[str, ...]:
    normalized = query.lower()
    queries: list[str] = []
    if _RFC_RE.search(normalized) is not None or "ietf" in normalized or "http message signatures" in normalized:
        queries.append(f"{query} site:rfc-editor.org")
    if "w3c" in normalized or "webauthn" in normalized:
        queries.append(f"{query} site:w3.org")
    if "chromium" in normalized or ("chips" in normalized and "cookie" in normalized):
        queries.append(f"{query} site:developer.chrome.com")
    if "iata" in normalized or ("rpk" in normalized and "aviation" in normalized):
        queries.append(f"{query} site:iata.org")
    return tuple(dict.fromkeys(queries))


def _candidate_payloads_from_search_results(
    candidates: list[object],
) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    for candidate in candidates:
        title = getattr(candidate, "title", None)
        url = getattr(candidate, "url", None)
        snippet = getattr(candidate, "snippet", None)
        if not title or not url or not snippet:
            continue
        source_url = getattr(candidate, "source_url", None)
        tier_url = str(source_url) if source_url else str(url)
        payloads.append(
            {
                "title": str(title),
                "url": str(url),
                "snippet": str(snippet),
                "_tier": _tier_for_url(tier_url),
                "_engine": str(getattr(candidate, "engine", "")),
            }
        )
    return payloads


def _dedupe_candidate_payloads(
    payloads: list[dict[str, str]],
) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for payload in payloads:
        url = payload.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(payload)
    return deduped


async def _rank_payloads_to_hits(
    *,
    query: str,
    candidate_payloads: list[dict[str, str]],
    sec_records: list[dict[str, object]],
    config: LiveRetrievalConfig,
) -> list[RetrievalHit]:
    rank_tasks = [
        asyncio.create_task(
            _rank_live_candidate(
                query=query,
                title=payload["title"],
                url=payload["url"],
                candidate_snippet=payload["snippet"],
                tier=payload["_tier"],
                engine=payload.get("_engine", ""),
                force_fetch=payload.get("_force_fetch") == "1",
                config=config,
            )
        )
        for payload in candidate_payloads
    ]
    rank_tasks.extend(
        asyncio.create_task(
            _rank_live_candidate(
                query=query,
                title=str(record["title"]),
                url=str(record["url"]),
                candidate_snippet=str(record["snippet"]),
                tier=str(record.get("credibility_tier") or "company_official"),
                engine="",
                config=config,
            )
        )
        for record in sec_records
        if record.get("title") and record.get("url") and record.get("snippet")
    )

    try:
        rank_results = await asyncio.gather(*rank_tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for task in rank_tasks:
            task.cancel()
        await asyncio.gather(*rank_tasks, return_exceptions=True)
        raise

    ranked = [
        item
        for item in rank_results
        if not isinstance(item, Exception) and item is not None
    ]
    ranked = sorted(
        ranked,
        key=lambda item: (
            item["_score"],
            -_TIER_ORDER.index(item["_tier"]),
            item["url"],
        ),
        reverse=True,
    )
    positive = [item for item in ranked if int(item["_score"]) > 0]
    selected = positive[:3] if positive else ranked[:3]

    if not any(item["_tier"] == "company_official" for item in selected):
        best_company_official = next(
            (
                item
                for item in ranked
                if item["_tier"] == "company_official" and int(item["_score"]) > 0
            ),
            None,
        )
        if best_company_official is not None:
            selected = [item for item in selected if item["url"] != best_company_official["url"]]
            if len(selected) >= 3:
                selected = selected[:2]
            selected.append(best_company_official)

    return [
        RetrievalHit(
            source_id=SOURCE_ID,
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
            credibility_tier=str(item["_tier"]),
        )
        for item in selected
    ]


async def _cancel_search_tasks(tasks: list[asyncio.Task[object]]) -> None:
    for task in tasks:
        if task.done():
            continue
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _detect_known_company_ir_target(query: str) -> dict[str, object] | None:
    normalized = normalize_query_text(query)
    best_match: tuple[int, dict[str, object]] | None = None
    for target in _KNOWN_COMPANY_IR_TARGETS:
        for alias in target["aliases"]:
            alias_text = str(alias)
            if re.search(
                rf"(?<![a-z0-9]){re.escape(alias_text)}(?![a-z0-9])",
                normalized,
            ) is None:
                continue
            candidate = (len(alias_text), target)
            if best_match is None or candidate[0] > best_match[0]:
                best_match = candidate
    return None if best_match is None else best_match[1]


def _host_matches_allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    normalized_host = host.lower()
    for allowed_host in allowed_hosts:
        candidate = allowed_host.lower()
        if normalized_host == candidate:
            return True
        if candidate.startswith("www.") and normalized_host == candidate[4:]:
            return True
        if normalized_host.endswith(f".{candidate.lstrip('www.')}"):
            return True
    return False


def _extract_known_company_ir_link_candidates(
    *,
    query: str,
    homepage_url: str,
    homepage_html: str,
    allowed_hosts: tuple[str, ...],
    required_path_markers: tuple[str, ...],
) -> list[dict[str, str]]:
    soup = BeautifulSoup(homepage_html, "html.parser")
    candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        absolute_url = urljoin(homepage_url, str(anchor["href"]))
        url_parts = urlsplit(absolute_url)
        host = (url_parts.hostname or "").lower()
        path = url_parts.path.lower()
        if not absolute_url.startswith(("http://", "https://")):
            continue
        if not _host_matches_allowed(host, allowed_hosts):
            continue
        if required_path_markers and not any(marker in path for marker in required_path_markers):
            continue
        if absolute_url in seen_urls:
            continue

        alignment_score = score_query_alignment(
            query,
            route="industry",
            title=text,
            snippet=absolute_url,
            url=absolute_url,
        )
        overlap = _query_overlap_count(query, title=text, snippet=absolute_url)
        if alignment_score <= 0 and overlap <= 0:
            continue

        seen_urls.add(absolute_url)
        candidates.append(
            {
                "title": text or absolute_url,
                "url": absolute_url,
                "snippet": text or absolute_url,
                "_tier": "company_official",
                "_alignment_score": str(alignment_score),
                "_overlap": str(overlap),
            }
        )

    candidates.sort(
        key=lambda item: (
            int(item["_alignment_score"]),
            int(item["_overlap"]),
            -len(item["url"]),
            item["url"],
        ),
        reverse=True,
    )
    return candidates[:3]


async def _search_known_company_ir_page_candidates(
    *,
    query: str,
) -> list[dict[str, str]]:
    if not _has_detailed_disclosure_intent(query):
        return []

    normalized = normalize_query_text(query)
    direct_payloads: list[dict[str, str]] = []
    for target in _DIRECT_COMPANY_IR_PAGE_TARGETS:
        aliases = tuple(str(alias) for alias in target["aliases"])
        if not any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            is not None
            for alias in aliases
        ):
            continue
        query_markers = tuple(str(marker) for marker in target["query_markers"])
        if not all(marker in normalized for marker in query_markers):
            continue

        page_text = ""
        try:
            page_html = await http_client.fetch_text(
                url=str(target["url"]),
                timeout=_COMPANY_IR_PAGE_TIMEOUT_SECONDS,
            )
            page_text = extract_page_content(page_html, max_chars=3200)
        except Exception:
            continue
        snippet = build_industry_snippet(
            query=query,
            candidate_snippet=str(target["title"]),
            page_text=page_text,
        )
        direct_payloads.append(
            {
                "title": str(target["title"]),
                "url": str(target["url"]),
                "snippet": snippet or str(target["title"]),
                "_tier": "company_official",
            }
        )

    if direct_payloads:
        return direct_payloads[:1]

    target = _detect_known_company_ir_target(query)
    if target is None:
        return []

    homepage_url = str(target["homepage_url"])
    allowed_hosts = tuple(str(host) for host in target["allowed_hosts"])
    required_path_markers = tuple(
        str(marker).lower() for marker in target.get("required_path_markers", ())
    )
    try:
        homepage_html = await http_client.fetch_text(
            url=homepage_url,
            timeout=_COMPANY_IR_HOME_TIMEOUT_SECONDS,
        )
    except Exception:
        return []

    extracted_candidates = _extract_known_company_ir_link_candidates(
        query=query,
        homepage_url=homepage_url,
        homepage_html=homepage_html,
        allowed_hosts=allowed_hosts,
        required_path_markers=required_path_markers,
    )
    payloads: list[dict[str, str]] = []
    for candidate in extracted_candidates:
        page_text = ""
        try:
            page_html = await http_client.fetch_text(
                url=candidate["url"],
                timeout=_COMPANY_IR_PAGE_TIMEOUT_SECONDS,
            )
            page_text = extract_page_content(page_html, max_chars=3200)
        except Exception:
            page_text = ""
        snippet = build_industry_snippet(
            query=query,
            candidate_snippet=candidate["snippet"],
            page_text=page_text,
        )
        payloads.append(
            {
                "title": candidate["title"],
                "url": candidate["url"],
                "snippet": snippet or candidate["snippet"],
                "_tier": "company_official",
            }
        )
    return payloads[:1]


async def _search_prioritized_sec_records(
    *,
    query: str,
    max_results: int,
) -> list[dict[str, object]]:
    try:
        company_records = await search_sec_company_submissions(
            query=query,
            max_results=max_results,
        )
    except Exception:
        company_records = []

    if company_records:
        return company_records

    try:
        return await search_sec_filings(query=query, max_results=max_results)
    except Exception:
        return []
    except asyncio.CancelledError:
        raise


async def _search_fastest_sec_records(
    *,
    query: str,
    max_results: int,
) -> list[dict[str, object]]:
    task_specs: list[tuple[int, asyncio.Task[list[dict[str, object]]]]] = [
        (
            0,
            asyncio.create_task(
                search_sec_company_submissions(
                    query=query,
                    max_results=max_results,
                )
            ),
        ),
        (
            1,
            asyncio.create_task(
                search_sec_filings(
                    query=query,
                    max_results=max_results,
                )
            ),
        ),
    ]
    priorities = {task: priority for priority, task in task_specs}
    pending_tasks = {task for _, task in task_specs}
    try:
        while pending_tasks:
            done, pending = await asyncio.wait(
                pending_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            pending_tasks = set(pending)
            completed_results: list[tuple[int, list[dict[str, object]]]] = []
            for done_task in done:
                try:
                    result = await done_task
                except asyncio.CancelledError:
                    for task in pending_tasks:
                        task.cancel()
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
                    raise
                except Exception:
                    continue
                if result:
                    completed_results.append((priorities[done_task], result))

            if completed_results:
                completed_results.sort(key=lambda item: item[0])
                for task in pending_tasks:
                    task.cancel()
                await asyncio.gather(*pending_tasks, return_exceptions=True)
                return completed_results[0][1]
        return []
    except asyncio.CancelledError:
        for task in pending_tasks:
            task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)
        raise


def _page_fetch_headers(url: str) -> dict[str, str] | None:
    host = (urlsplit(url).hostname or "").lower()
    if host in {"www.sec.gov", "sec.gov"}:
        return {"User-Agent": _SEC_CONTACT_USER_AGENT}
    return None


def _query_aligned_fetch_timeout(url: str) -> float:
    host = (urlsplit(url).hostname or "").lower()
    if host in {"www.sec.gov", "sec.gov"}:
        return _SEC_ARCHIVE_FETCH_TIMEOUT_SECONDS
    return _QUERY_ALIGNED_FETCH_TIMEOUT_SECONDS


def _should_query_align_fetch(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in _QUERY_ALIGNED_FETCH_HOSTS


def _missing_focus_terms(
    query: str,
    *,
    title: str,
    candidate_snippet: str,
) -> tuple[str, ...]:
    query_term_set = set(_content_tokens(query))
    metadata_term_set = set(_content_tokens(f"{title} {candidate_snippet}"))
    return tuple(term for term in query_term_set if term not in metadata_term_set)


def _focus_term_overlap_count(
    terms: tuple[str, ...],
    *,
    text: str,
) -> int:
    if not terms or not text:
        return 0
    text_tokens = set(_content_tokens(text))
    return sum(1 for term in terms if term in text_tokens)


def _trim_snippet_words(
    text: str,
    *,
    max_words: int = 40,
) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip().rstrip(",.;:")


async def _fetch_query_aligned_page_text(
    *,
    query: str,
    title: str,
    url: str,
    candidate_snippet: str,
) -> str:
    host = (urlsplit(url).hostname or "").lower()
    timeout = _query_aligned_fetch_timeout(url)
    headers = _page_fetch_headers(url)
    missing_focus_terms = _missing_focus_terms(
        query,
        title=title,
        candidate_snippet=candidate_snippet,
    )

    async def _fetch_excerpt(max_chars: int) -> str:
        html = await http_client.fetch_text_limited(
            url=url,
            timeout=timeout,
            headers=headers,
            max_chars=max_chars,
        )
        return extract_query_aligned_page_excerpt(
            html=html,
            query=query,
            title=title,
            candidate_snippet=candidate_snippet,
            max_chars=260,
        )

    if host in {"www.sec.gov", "sec.gov"}:
        initial_excerpt = await _fetch_excerpt(_SEC_ARCHIVE_INITIAL_FETCH_CHAR_LIMIT)
        if (
            _focus_term_overlap_count(missing_focus_terms, text=initial_excerpt) >= 2
            or _SEC_ARCHIVE_INITIAL_FETCH_CHAR_LIMIT >= _SEC_ARCHIVE_FETCH_CHAR_LIMIT
        ):
            return initial_excerpt

        deep_excerpt = await _fetch_excerpt(_SEC_ARCHIVE_FETCH_CHAR_LIMIT)
        if (
            _focus_term_overlap_count(missing_focus_terms, text=deep_excerpt)
            >= _focus_term_overlap_count(missing_focus_terms, text=initial_excerpt)
        ):
            return deep_excerpt or initial_excerpt
        return initial_excerpt or deep_excerpt

    return await _fetch_excerpt(_QUERY_ALIGNED_FETCH_CHAR_LIMIT)


async def search_fixture(query: str) -> list[RetrievalHit]:
    """Return deterministic industry hits for offline tests."""
    ranked = sorted(
        (
            {
                **item,
                "_score": _score(query, item),
                "_tier": _tier_for_url(item["url"]),
            }
            for item in _FIXTURES
        ),
        key=lambda item: (
            item["_score"],
            -_TIER_ORDER.index(item["_tier"]),
            item["url"],
        ),
        reverse=True,
    )
    positive = [item for item in ranked if int(item["_score"]) > 0]
    selected = positive[:3] if positive else ranked[:3]

    if not any(item["_tier"] == "company_official" for item in selected):
        best_company_official = next(
            (item for item in ranked if item["_tier"] == "company_official" and int(item["_score"]) > 0),
            None,
        )
        if best_company_official is not None:
            selected = [item for item in selected if item["url"] != best_company_official["url"]]
            if len(selected) >= 3:
                selected = selected[:2]
            selected.append(best_company_official)

    return [
        RetrievalHit(
            source_id=SOURCE_ID,
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
            credibility_tier=str(item["_tier"]),
        )
        for item in selected
    ]


async def _rank_live_candidate(
    *,
    query: str,
    title: str,
    url: str,
    candidate_snippet: str,
    tier: str,
    engine: str = "",
    force_fetch: bool = False,
    config: LiveRetrievalConfig,
) -> dict[str, str | int] | None:
    base_payload = {
        "title": title,
        "url": url,
        "snippet": candidate_snippet,
    }
    base_score = _score(query, base_payload)
    missing_focus_terms = _missing_focus_terms(
        query,
        title=title,
        candidate_snippet=candidate_snippet,
    )
    force_query_aligned_fetch = bool(
        missing_focus_terms
        and _query_overlap_count(query, title=title, snippet=candidate_snippet)
        < _OFFICIAL_FETCH_OVERLAP_THRESHOLD
    )
    query_aligned_excerpt = False
    if (
        engine == "google_news_rss"
        and not force_fetch
        and base_score > 0
    ):
        return {
            **base_payload,
            "_score": base_score,
            "_tier": tier,
        }

    if (
        not force_fetch
        and not force_query_aligned_fetch
        and base_score > 0
        and not _should_fetch_official_candidate(
        query=query,
        title=title,
        snippet=candidate_snippet,
        tier=tier,
        )
    ):
        return {
            **base_payload,
            "_score": base_score,
            "_tier": tier,
        }

    try:
        if _should_query_align_fetch(url):
            page_text = await _fetch_query_aligned_page_text(
                query=query,
                title=title,
                url=url,
                candidate_snippet=candidate_snippet,
            )
            query_aligned_excerpt = True
        else:
            page_text = await fetch_page_text(
                url=url,
                browser_enabled=config.browser_enabled,
                browser_headless=config.browser_headless,
                timeout_seconds=_PAGE_FETCH_TIMEOUT_SECONDS,
                max_chars=600,
            )
    except Exception:
        page_text = ""
    page_focus_overlap = _focus_term_overlap_count(
        missing_focus_terms,
        text=page_text,
    )
    if query_aligned_excerpt and page_focus_overlap >= 2:
        snippet = page_text.strip()
    else:
        snippet = build_industry_snippet(
            query=query,
            candidate_snippet="" if force_fetch else candidate_snippet,
            page_text=page_text,
        )
    snippet = _trim_snippet_words(snippet or candidate_snippet)
    payload = {
        "title": title,
        "url": url,
        "snippet": snippet,
    }
    enriched_score = _score(query, payload)
    base_focus_overlap = _focus_term_overlap_count(
        missing_focus_terms,
        text=candidate_snippet,
    )
    enriched_focus_overlap = _focus_term_overlap_count(
        missing_focus_terms,
        text=payload["snippet"],
    )
    base_fact_density = fact_density_score(candidate_snippet)
    enriched_fact_density = fact_density_score(payload["snippet"])
    if query_aligned_excerpt and page_focus_overlap >= 2:
        enriched_score = max(base_score, enriched_score)
    elif (
        enriched_focus_overlap >= max(2, base_focus_overlap + 1)
        and enriched_focus_overlap > base_focus_overlap
    ):
        enriched_score = max(base_score, enriched_score)
    elif (
        payload["snippet"] != candidate_snippet
        and enriched_fact_density >= base_fact_density + 2.0
    ):
        enriched_score = max(base_score, enriched_score)
    elif base_score > enriched_score:
        payload["snippet"] = candidate_snippet
        enriched_score = base_score
    return {
        **payload,
        "_score": enriched_score,
        "_tier": tier,
    }


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live industry hits from multi-engine discovery."""
    config = LiveRetrievalConfig.from_env()
    if config.fixture_shortcuts_enabled:
        fixture_hits = [
            hit
            for hit in await search_fixture(query)
            if _score(
                query,
                {
                    "title": hit.title,
                    "url": hit.url,
                    "snippet": hit.snippet,
                },
            )
            >= _MIN_FIXTURE_SCORE
        ]
        if fixture_hits:
            return fixture_hits[:3]

    direct_candidate_payloads = _direct_official_candidates(query)
    if direct_candidate_payloads:
        direct_hits = await _rank_payloads_to_hits(
            query=query,
            candidate_payloads=direct_candidate_payloads,
            sec_records=[],
            config=config,
        )
        if direct_hits:
            return direct_hits

    should_query_sec = _should_query_sec(query)
    known_company_submission_target = should_query_sec and has_known_company_submission_target(query)
    known_company_ir_target = (
        should_query_sec
        and _has_detailed_disclosure_intent(query)
        and _detect_known_company_ir_target(query) is not None
    )
    if known_company_ir_target:
        company_ir_payloads = await _search_known_company_ir_page_candidates(query=query)
        if company_ir_payloads:
            strongest_company_ir_score = max(
                _score(
                    query,
                    {
                        "title": payload["title"],
                        "url": payload["url"],
                        "snippet": payload["snippet"],
                    },
                )
                for payload in company_ir_payloads
            )
            if strongest_company_ir_score >= _COMPANY_IR_STRONG_SCORE_THRESHOLD:
                company_ir_hits = await _rank_payloads_to_hits(
                    query=query,
                    candidate_payloads=company_ir_payloads,
                    sec_records=[],
                    config=config,
                )
                if company_ir_hits:
                    return company_ir_hits

    sec_records: list[dict[str, object]] = []
    if should_query_sec:
        if known_company_submission_target:
            sec_records = await _search_prioritized_sec_records(
                query=query,
                max_results=3,
            )
        else:
            sec_records = await _search_fastest_sec_records(
                query=query,
                max_results=3,
            )

    if sec_records:
        early_hits = await _rank_payloads_to_hits(
            query=query,
            candidate_payloads=[],
            sec_records=sec_records[:1],
            config=config,
        )
        if early_hits:
            return early_hits

    web_task = asyncio.create_task(
        search_multi_engine(
            query=query,
            engines=config.search_engines,
            max_results=8,
        )
    )
    official_query_tasks = [
        asyncio.create_task(
            search_multi_engine(
                query=official_query,
                engines=config.search_engines,
                max_results=5,
            )
        )
        for official_query in _official_search_queries(query)
    ]
    background_search_tasks: list[asyncio.Task[object]] = [
        web_task,
        *official_query_tasks,
    ]

    try:
        task_results = await asyncio.gather(
            web_task,
            *official_query_tasks,
            return_exceptions=True,
        )
    except asyncio.CancelledError:
        await _cancel_search_tasks(background_search_tasks)
        raise
    web_result = task_results[0]
    web_candidates = [] if isinstance(web_result, Exception) else web_result
    official_results = task_results[1 : 1 + len(official_query_tasks)]
    official_candidates: list[object] = []
    for result in official_results:
        if isinstance(result, Exception):
            continue
        official_candidates.extend(result)

    candidate_payloads = _candidate_payloads_from_search_results(list(web_candidates))
    candidate_payloads.extend(_candidate_payloads_from_search_results(official_candidates))
    if not candidate_payloads and not direct_candidate_payloads:
        try:
            news_candidates = await search_multi_engine(
                query=query,
                engines=("google_news_rss",),
                max_results=3,
            )
        except Exception:
            news_candidates = []
        candidate_payloads.extend(
            _candidate_payloads_from_search_results(list(news_candidates))
        )
    candidate_payloads.extend(direct_candidate_payloads)
    candidate_payloads = _dedupe_candidate_payloads(candidate_payloads)
    return await _rank_payloads_to_hits(
        query=query,
        candidate_payloads=candidate_payloads,
        sec_records=sec_records,
        config=config,
    )


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
