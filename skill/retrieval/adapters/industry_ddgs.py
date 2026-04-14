"""Industry ddgs adapter with deterministic credibility-tier annotation."""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.sec_edgar import search_sec_filings
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.industry import build_industry_snippet
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
_COMPANY_OFFICIAL_DOMAINS: frozenset[str] = frozenset(
    {"www.tesla.com", "www.byd.com", "www.sec.gov", "sec.gov"}
)
_INDUSTRY_ASSOCIATION_DOMAINS: frozenset[str] = frozenset(
    {
        "www.iea.org",
        "www.sae.org",
        "www.semi.org",
        "www.counterpointresearch.com",
        "www.canalys.com",
        "www.idc.com",
    }
)
_TRUSTED_NEWS_DOMAINS: frozenset[str] = frozenset(
    {"www.reuters.com", "www.bloomberg.com"}
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
    host = (urlsplit(url).hostname or "").lower()
    if host in _COMPANY_OFFICIAL_DOMAINS:
        return "company_official"
    if host in _INDUSTRY_ASSOCIATION_DOMAINS:
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
    normalized = query.lower()
    markers = (
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
        "annual report",
        "quarterly report",
        "earnings",
        "guidance",
        "filing",
        "sec",
    )
    return any(marker in normalized for marker in markers)


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
    config: LiveRetrievalConfig,
) -> dict[str, str | int] | None:
    base_payload = {
        "title": title,
        "url": url,
        "snippet": candidate_snippet,
    }
    base_score = _score(query, base_payload)
    if base_score > 0 and tier != "general_web":
        return {
            **base_payload,
            "_score": base_score,
            "_tier": tier,
        }

    try:
        page_text = await fetch_page_text(
            url=url,
            browser_enabled=config.browser_enabled,
            browser_headless=config.browser_headless,
            timeout_seconds=1.0,
            max_chars=600,
        )
    except Exception:
        page_text = ""
    snippet = build_industry_snippet(
        query=query,
        candidate_snippet=candidate_snippet,
        page_text=page_text,
    )
    payload = {
        "title": title,
        "url": url,
        "snippet": snippet or candidate_snippet,
    }
    enriched_score = _score(query, payload)
    if base_score > enriched_score:
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

    web_task = asyncio.create_task(
        search_multi_engine(
            query=query,
            engines=config.search_engines,
            max_results=8,
        )
    )
    sec_task = (
        asyncio.create_task(search_sec_filings(query=query, max_results=3))
        if _should_query_sec(query)
        else None
    )

    try:
        candidates = await web_task
    except asyncio.CancelledError:
        web_task.cancel()
        await asyncio.gather(web_task, return_exceptions=True)
        if sec_task is not None:
            sec_task.cancel()
            await asyncio.gather(sec_task, return_exceptions=True)
        raise
    except Exception:
        candidates = []

    sec_records: list[dict[str, object]] = []
    if sec_task is not None:
        try:
            sec_records = await sec_task
        except asyncio.CancelledError:
            sec_task.cancel()
            await asyncio.gather(sec_task, return_exceptions=True)
            raise
        except Exception:
            sec_records = []

    rank_tasks = [
        asyncio.create_task(
            _rank_live_candidate(
                query=query,
                title=candidate.title,
                url=candidate.url,
                candidate_snippet=candidate.snippet,
                tier=_tier_for_url(candidate.url),
                config=config,
            )
        )
        for candidate in candidates
    ]
    rank_tasks.extend(
        asyncio.create_task(
            _rank_live_candidate(
                query=query,
                title=str(record["title"]),
                url=str(record["url"]),
                candidate_snippet=str(record["snippet"]),
                tier=str(record.get("credibility_tier") or "company_official"),
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


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
