"""Official policy registry adapter with deterministic fixture output."""

from __future__ import annotations

from typing import Any

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.policy import (
    extract_policy_metadata,
    is_official_policy_url,
    preferred_policy_domains,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "policy_official_registry"
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "数据出境安全评估办法（2025修订版）",
        "url": "https://www.cac.gov.cn/2025-03/21/c_1742512000001.htm",
        "snippet": "2025修订版明确新增年度风险自评估要求，并调整申报材料、触发阈值和流程时限。",
        "authority": "国家互联网信息办公室",
        "jurisdiction": "CN",
        "publication_date": "2025-03-21",
        "effective_date": "2025-04-01",
        "version": "2025修订版",
    },
    {
        "title": "数据出境安全评估办法修订说明",
        "url": "https://www.cac.gov.cn/2025-03/21/c_1742512000002.htm",
        "snippet": "官方说明列出新增安全评估材料，调整适用范围，并解释重点变化条款。",
        "authority": "国家互联网信息办公室",
        "jurisdiction": "CN",
        "publication_date": "2025-03-21",
        "effective_date": "2025-04-01",
        "version": "2025说明版",
    },
    {
        "title": "个人信息出境认证办法（2025修订版）",
        "url": "https://www.cac.gov.cn/2025-02/14/c_1742512000003.htm",
        "snippet": "2025修订版更新认证范围，并修订认证材料、持续监督和责任条款。",
        "authority": "国家互联网信息办公室",
        "jurisdiction": "CN",
        "publication_date": "2025-02-14",
        "effective_date": "2025-03-01",
        "version": "2025修订版",
    },
    {
        "title": "个人信息出境认证办法条款修订解读",
        "url": "https://www.cac.gov.cn/2025-02/14/c_1742512000004.htm",
        "snippet": "官方解读说明条款修订集中在适用主体、认证流程、材料清单和持续审查要求。",
        "authority": "国家互联网信息办公室",
        "jurisdiction": "CN",
        "publication_date": "2025-02-14",
        "effective_date": "2025-03-01",
        "version": "2025解读版",
    },
    {
        "title": "促进和规范数据跨境流动规定",
        "url": "https://www.gov.cn/zhengce/2025-01/09/content_data_cross_border.htm",
        "snippet": "规定明确列出可豁免场景，包括国际贸易、跨境运输、学术合作和紧急救助中的必要数据传输。",
        "authority": "国务院",
        "jurisdiction": "CN",
        "publication_date": "2025-01-09",
        "effective_date": "2025-02-01",
        "version": "2025正式版",
    },
    {
        "title": "AI Act 开源模型义务说明",
        "url": "https://eur-lex.europa.eu/ai-act-open-source-obligations",
        "snippet": "AI Act 明确开源模型的透明度义务、免责边界和产业落地合规要求。",
        "authority": "European Parliament",
        "jurisdiction": "EU",
        "publication_date": "2026-03-12",
        "effective_date": "2026-08-01",
        "version": "AI Act implementation note",
    },
    {
        "title": "欧盟碳关税政策与新能源车出口规则",
        "url": "https://taxation-customs.ec.europa.eu/cbam-nev-export-policy",
        "snippet": "欧盟碳关税政策细化新能源车出口申报、核算规则，并影响跨境供应链安排。",
        "authority": "European Commission",
        "jurisdiction": "EU",
        "publication_date": "2026-02-18",
        "effective_date": "2026-07-01",
        "version": "2026 CBAM vehicle guidance",
    },
    {
        "title": "美国出口管制规则与训练芯片供给",
        "url": "https://www.bis.gov/ai-training-chip-export-control-rule-2026",
        "snippet": "美国出口管制规则收紧大模型训练芯片出口，并直接影响高端芯片供给与许可安排。",
        "authority": "U.S. Department of Commerce",
        "jurisdiction": "US",
        "publication_date": "2026-04-02",
        "effective_date": "2026-04-15",
        "version": "2026 training chip rule",
    },
    {
        "title": "Ministry of Ecology and Environment policy bulletin",
        "url": "https://www.mee.gov.cn/policy/latest-regulation",
        "snippet": "Official regulatory bulletin for environmental compliance.",
        "authority": "Ministry of Ecology and Environment",
        "jurisdiction": "CN",
        "publication_date": "2026-03-18",
        "effective_date": "2026-04-01",
        "version": "2026-03 bulletin",
    },
    {
        "title": "State Council administrative regulation repository update",
        "url": "https://www.gov.cn/zhengce/content/official-update.htm",
        "snippet": "Authoritative policy text with publication references.",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2026-02-21",
        "effective_date": "2026-03-01",
    },
    {
        "title": "State Council autonomous driving pilot regulation",
        "url": "https://www.gov.cn/zhengce/autonomous-driving-pilot-regulation",
        "snippet": "Official autonomous driving pilot regulation sets 2026 compliance requirements for road testing.",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2026-03-28",
        "effective_date": "2026-05-01",
        "version": "2026 pilot edition",
    },
    {
        "title": "Ministry of Commerce AI chip export controls notice",
        "url": "https://www.mofcom.gov.cn/article/ai-chip-export-controls-2026",
        "snippet": "Official AI chip export controls notice tightens 2026 licensing requirements for advanced accelerators.",
        "authority": "Ministry of Commerce",
        "jurisdiction": "CN",
        "publication_date": "2026-04-02",
        "effective_date": "2026-04-15",
        "version": "2026 export control notice",
    },
)


def _score(query: str, fixture: dict[str, Any]) -> int:
    return score_query_alignment(
        query,
        route="policy",
        title=str(fixture["title"]),
        snippet=str(fixture["snippet"]),
        url=str(fixture["url"]),
        authority=str(fixture["authority"]),
        publication_date=str(fixture["publication_date"]),
        effective_date=str(fixture["effective_date"]),
        version=str(fixture["version"]) if fixture.get("version") is not None else None,
    )


async def search_fixture(query: str) -> list[RetrievalHit]:
    """Return deterministic official-policy hits for offline tests."""
    ranked = sorted(
        _FIXTURES,
        key=lambda item: (_score(query, item), item["url"]),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            authority=str(item["authority"]),
            jurisdiction=str(item["jurisdiction"]),
            publication_date=str(item["publication_date"]),
            effective_date=str(item["effective_date"]),
            version=str(item["version"]) if item.get("version") is not None else None,
        )
        for item in ranked
    ]


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live official-policy hits discovered on official domains."""
    config = LiveRetrievalConfig.from_env()
    seen_urls: set[str] = set()
    candidates = []
    for domain in preferred_policy_domains(query, fallback=False):
        try:
            discovered = await search_multi_engine(
                query=f"{query} site:{domain}",
                engines=config.search_engines,
                max_results=4,
            )
        except Exception:
            continue
        for item in discovered:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            candidates.append(item)

    ranked = []
    for candidate in candidates:
        if not is_official_policy_url(candidate.url):
            continue
        try:
            page_text = await fetch_page_text(
                url=candidate.url,
                browser_enabled=config.browser_enabled,
                browser_headless=config.browser_headless,
                timeout_seconds=6.0,
                max_chars=1200,
            )
        except Exception:
            page_text = ""
        metadata = extract_policy_metadata(url=candidate.url, page_text=page_text)
        if metadata["authority"] is None or (
            metadata["publication_date"] is None and metadata["effective_date"] is None
        ):
            continue
        payload = {
            "title": candidate.title,
            "url": candidate.url,
            "snippet": candidate.snippet or page_text[:320],
            "authority": metadata["authority"],
            "publication_date": metadata["publication_date"],
            "effective_date": metadata["effective_date"],
            "version": metadata["version"],
        }
        ranked.append(
            {
                **payload,
                "_jurisdiction": metadata["jurisdiction"],
                "_score": _score(query, payload),
                "_metadata_bonus": int(metadata["version"] is not None)
                + int(metadata["effective_date"] is not None)
                + int(metadata["publication_date"] is not None),
            }
        )

    ranked.sort(
        key=lambda item: (
            item["_score"],
            item["_metadata_bonus"],
            item["url"],
        ),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            authority=str(item["authority"]) if item["authority"] is not None else None,
            jurisdiction=str(item["_jurisdiction"]) if item["_jurisdiction"] is not None else None,
            publication_date=str(item["publication_date"]) if item["publication_date"] is not None else None,
            effective_date=str(item["effective_date"]) if item["effective_date"] is not None else None,
            version=str(item["version"]) if item["version"] is not None else None,
        )
        for item in ranked[:5]
    ]


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
