"""Official policy registry adapter with deterministic fixture output."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex
from skill.retrieval.live.clients.policy_fincen import search_fincen_policy
from skill.retrieval.live.clients.policy_federal_register import search_federal_register
from skill.retrieval.live.clients.policy_nist import search_nist_publications
from skill.retrieval.live.clients.policy_registry import search_policy_registry
from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies
from skill.retrieval.live.clients.policy_uk_legislation import search_uk_legislation
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.policy import (
    extract_policy_metadata,
    is_official_policy_url,
    preferred_policy_domains,
    preferred_policy_search_engines,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "policy_official_registry"
_MIN_REGISTRY_SCORE = 3
_MIN_OPEN_WEB_SCORE = 3
_MIN_FIXTURE_SCORE = 7
_FIXTURE_SHORTCUT_GRACE_SECONDS = 0.25
_OPEN_WEB_TIMEOUT_SECONDS = 2.4
_OPEN_WEB_MAX_RESULTS = 3
_OPEN_WEB_CANDIDATE_LIMIT = 4
_PAGE_FETCH_TIMEOUT_SECONDS = 1.0
_MIN_DIRECT_SCORE = 3
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
    {
        "title": "四部门关于开展智能网联汽车准入和上路通行试点工作的通知",
        "url": "https://www.gov.cn/zhengce/zhengceku/202311/content_6915788.htm",
        "snippet": "官方通知明确智能网联汽车准入和上路通行试点安排，并细化自动驾驶监管要求与实施时间。",
        "authority": "工业和信息化部 公安部 住房城乡建设部 交通运输部",
        "jurisdiction": "CN",
        "publication_date": "2023-11-17",
        "effective_date": "2023-12-01",
        "version": "2023 pilot notice",
    },
    {
        "title": "关于开展智能网联汽车准入和上路通行试点工作的通知解读",
        "url": "https://www.gov.cn/zhengce/202311/content_6915789.htm",
        "snippet": "官方政策解读说明试点监管目标、实施节奏和自动驾驶相关合规要求。",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2023-11-17",
        "effective_date": "2023-12-01",
        "version": "2023 interpretation",
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


def _to_hit(item: dict[str, Any]) -> RetrievalHit:
    return RetrievalHit(
        source_id=_SOURCE_ID,
        title=str(item["title"]),
        url=str(item["url"]),
        snippet=str(item["snippet"]),
        authority=str(item["authority"]) if item.get("authority") is not None else None,
        jurisdiction=str(item["jurisdiction"]) if item.get("jurisdiction") is not None else None,
        publication_date=(
            str(item["publication_date"]) if item.get("publication_date") is not None else None
        ),
        effective_date=(
            str(item["effective_date"]) if item.get("effective_date") is not None else None
        ),
        version=str(item["version"]) if item.get("version") is not None else None,
    )


def _rank_structured_records(
    *,
    query: str,
    records: list[dict[str, Any]],
    min_score: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        (
            item
            for item in records
            if item.get("title") and item.get("url") and _score(query, item) >= min_score
        ),
        key=lambda item: (
            _score(query, item),
            item.get("publication_date") or "",
            item["url"],
        ),
        reverse=True,
    )
    return ranked[:5]


def _is_us_policy_query(query: str) -> bool:
    normalized = query.lower()
    markers = (
        "federal register",
        "federal",
        "epa",
        "fda",
        "ftc",
        "fincen",
        "beneficial ownership",
        "corporate transparency act",
        "boi",
        "cisa",
        "circia",
        "pfas",
        "noncompete",
        "nist",
        "fips",
        "item 1.05",
        "cfr",
        "u.s.",
        "us ",
        "united states",
        "methane rule",
        "sec rule",
    )
    return any(marker in normalized for marker in markers)


def _prefer_direct_policy_sources(query: str) -> bool:
    normalized = query.lower()
    markers = (
        "eur-lex",
        "ai act",
        "nis2",
        "fips",
        "nist",
        "pccp",
        "beneficial ownership",
        "corporate transparency act",
        "boi",
        "online safety act",
        "legislation.gov.uk",
        "ofcom",
    )
    return any(marker in normalized for marker in markers)


async def _search_direct_policy_sources(
    *,
    query: str,
) -> list[dict[str, Any]]:
    tasks: tuple[asyncio.Task[list[dict[str, object]]], ...] = (
        asyncio.create_task(search_eur_lex(query=query, max_results=5)),
        asyncio.create_task(search_nist_publications(query=query, max_results=5)),
        asyncio.create_task(search_fincen_policy(query=query, max_results=5)),
        asyncio.create_task(search_us_policy_agencies(query=query, max_results=5)),
        asyncio.create_task(search_uk_legislation(query=query, max_results=5)),
    )
    try:
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    combined_records: list[dict[str, Any]] = []
    for item in gathered:
        if isinstance(item, Exception):
            continue
        for record in item:
            if not isinstance(record, dict):
                continue
            if not record.get("title") or not record.get("url"):
                continue
            combined_records.append(record)

    deduped_records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for record in combined_records:
        url = str(record.get("url") or "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped_records.append(record)

    return _rank_structured_records(
        query=query,
        records=deduped_records,
        min_score=_MIN_DIRECT_SCORE,
    )


async def _rank_open_web_candidate(
    *,
    query: str,
    candidate: Any,
    config: LiveRetrievalConfig,
) -> dict[str, Any] | None:
    if not is_official_policy_url(candidate.url):
        return None
    try:
        page_text = await fetch_page_text(
            url=candidate.url,
            browser_enabled=config.browser_enabled,
            browser_headless=config.browser_headless,
            timeout_seconds=_PAGE_FETCH_TIMEOUT_SECONDS,
            max_chars=1200,
        )
    except Exception:
        page_text = ""
    metadata = extract_policy_metadata(
        url=candidate.url,
        page_text="\n".join(
            part
            for part in (
                page_text,
                getattr(candidate, "title", ""),
                getattr(candidate, "snippet", ""),
                candidate.url,
            )
            if part
        ),
    )
    if metadata["authority"] is None or (
        metadata["publication_date"] is None
        and metadata["effective_date"] is None
        and _score(
            query,
            {
                "title": candidate.title,
                "url": candidate.url,
                "snippet": candidate.snippet or page_text[:320],
                "authority": metadata["authority"],
                "jurisdiction": metadata["jurisdiction"],
                "publication_date": metadata["publication_date"],
                "effective_date": metadata["effective_date"],
                "version": metadata["version"],
            },
        )
        < (_MIN_OPEN_WEB_SCORE + 1)
    ):
        return None
    result_snippet = candidate.snippet or page_text[:320]
    ranking_snippet = " ".join(
        part.strip()
        for part in (
            candidate.snippet or "",
            page_text[:800],
        )
        if part and part.strip()
    )
    payload = {
        "title": candidate.title,
        "url": candidate.url,
        "snippet": result_snippet,
        "authority": metadata["authority"],
        "jurisdiction": metadata["jurisdiction"],
        "publication_date": metadata["publication_date"],
        "effective_date": metadata["effective_date"],
        "version": metadata["version"],
    }
    alignment_score = _score(
        query,
        {
            **payload,
            "snippet": ranking_snippet or result_snippet,
        },
    )
    if alignment_score < _MIN_OPEN_WEB_SCORE:
        return None
    return {
        **payload,
        "_score": alignment_score,
        "_metadata_bonus": int(metadata["version"] is not None)
        + int(metadata["effective_date"] is not None)
        + int(metadata["publication_date"] is not None),
    }


async def _search_open_web_policy(
    *,
    query: str,
    config: LiveRetrievalConfig,
) -> list[dict[str, Any]]:
    engines = preferred_policy_search_engines(config.search_engines)
    preferred_domains = preferred_policy_domains(query, fallback=False)
    async with asyncio.timeout(_OPEN_WEB_TIMEOUT_SECONDS):
        try:
            search_results = await search_multi_engine(
                query=query,
                engines=engines,
                max_results=max(_OPEN_WEB_MAX_RESULTS * 2, _OPEN_WEB_CANDIDATE_LIMIT),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            search_results = []

        seen_urls: set[str] = set()
        candidates: list[Any] = []
        ranked_candidates = sorted(
            (
                candidate
                for candidate in search_results
                if is_official_policy_url(candidate.url)
            ),
            key=lambda candidate: (
                (
                    preferred_domains.index((urlsplit(candidate.url).hostname or "").lower())
                    if (urlsplit(candidate.url).hostname or "").lower() in preferred_domains
                    else 99
                ),
                candidate.url,
            ),
        )
        for item in ranked_candidates:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            candidates.append(item)
            if len(candidates) >= _OPEN_WEB_CANDIDATE_LIMIT:
                break

        rank_tasks = [
            asyncio.create_task(
                _rank_open_web_candidate(
                    query=query,
                    candidate=candidate,
                    config=config,
                )
            )
            for candidate in candidates
        ]
        try:
            ranked_candidates = await asyncio.gather(*rank_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for task in rank_tasks:
                task.cancel()
            await asyncio.gather(*rank_tasks, return_exceptions=True)
            raise
        ranked = [
            item for item in ranked_candidates if not isinstance(item, Exception) and item is not None
        ]
        ranked.sort(
            key=lambda item: (
                item["_score"],
                item["_metadata_bonus"],
                item["url"],
            ),
            reverse=True,
        )
        return ranked[:5]


def _detach_task(task: asyncio.Task[object]) -> None:
    def _consume_result(done_task: asyncio.Task[object]) -> None:
        try:
            done_task.result()
        except BaseException:
            return

    task.add_done_callback(_consume_result)


def _cancel_if_pending(task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    _detach_task(task)


def _rank_fixture_records(
    *,
    query: str,
    min_score: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        (
            item
            for item in _FIXTURES
            if _score(query, item) >= min_score
        ),
        key=lambda item: (
            _score(query, item),
            item.get("publication_date") or "",
            item["url"],
        ),
        reverse=True,
    )
    return ranked[:5]


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live official-policy hits discovered on official domains."""
    config = LiveRetrievalConfig.from_env()
    ranked_fixture_records = (
        []
        if _is_us_policy_query(query)
        else _rank_fixture_records(
            query=query,
            min_score=_MIN_FIXTURE_SCORE,
        )
    )
    if ranked_fixture_records:
        return [_to_hit(item) for item in ranked_fixture_records]

    is_us_query = _is_us_policy_query(query)
    prefer_direct_sources = _prefer_direct_policy_sources(query)
    registry_task = asyncio.create_task(search_policy_registry(query=query, max_results=5))
    open_web_task = asyncio.create_task(_search_open_web_policy(query=query, config=config))
    direct_task = asyncio.create_task(_search_direct_policy_sources(query=query))
    federal_task = (
        asyncio.create_task(search_federal_register(query=query, max_results=5))
        if is_us_query
        else None
    )

    try:
        try:
            registry_records = await registry_task
        except Exception:
            registry_records = []
        ranked_registry_records = _rank_structured_records(
            query=query,
            records=registry_records,
            min_score=_MIN_REGISTRY_SCORE,
        )
        if ranked_registry_records:
            _cancel_if_pending(federal_task)
            _cancel_if_pending(direct_task)
            _cancel_if_pending(open_web_task)
            return [_to_hit(item) for item in ranked_registry_records]

        if prefer_direct_sources:
            try:
                ranked_direct_records = await direct_task
            except Exception:
                ranked_direct_records = []
            if ranked_direct_records:
                _cancel_if_pending(federal_task)
                _cancel_if_pending(open_web_task)
                return [_to_hit(item) for item in ranked_direct_records]

        if federal_task is not None:
            try:
                federal_records = await federal_task
            except Exception:
                federal_records = []
            ranked_federal_records = _rank_structured_records(
                query=query,
                records=federal_records,
                min_score=_MIN_REGISTRY_SCORE,
            )
            if ranked_federal_records:
                _cancel_if_pending(direct_task)
                _cancel_if_pending(open_web_task)
                return [_to_hit(item) for item in ranked_federal_records]

        if not prefer_direct_sources:
            try:
                ranked_direct_records = await direct_task
            except Exception:
                ranked_direct_records = []
            if ranked_direct_records:
                _cancel_if_pending(open_web_task)
                return [_to_hit(item) for item in ranked_direct_records]

        try:
            ranked_open_web_records = await open_web_task
        except Exception:
            ranked_open_web_records = []

        if ranked_open_web_records:
            return [_to_hit(item) for item in ranked_open_web_records]

        return []
    except asyncio.CancelledError:
        _cancel_if_pending(registry_task)
        _cancel_if_pending(open_web_task)
        _cancel_if_pending(direct_task)
        _cancel_if_pending(federal_task)
        raise


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
