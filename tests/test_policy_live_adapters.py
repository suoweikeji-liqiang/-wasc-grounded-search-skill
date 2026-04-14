"""Contracts for live policy adapter implementations."""

from __future__ import annotations

import asyncio


def test_policy_registry_client_parses_gov_search_results(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients import policy_registry

    async def _fake_fetch_json(**kwargs: object) -> object:
        assert kwargs["url"] == "https://sousuo.www.gov.cn/search-gov/data"
        assert kwargs["params"]["t"] == "zhengcelibrary"
        assert kwargs["params"]["type"] == "gwyzcwjk"
        assert kwargs["params"]["searchfield"] == "title"
        return {
            "code": 200,
            "msg": "操作成功",
            "searchVO": {
                "catMap": {
                    "bumenfile": {
                        "listVO": [
                            {
                                "title": "五部门关于公布<em>智能</em><em>网联</em><em>汽车</em>“车路云一体化”应用<em>试点</em>城市名单的<em>通知</em>",
                                "url": "https://www.gov.cn/zhengce/zhengceku/202407/content_6965771.htm",
                                "summary": "工业和信息化部关于公布智能网联汽车试点城市名单的通知。",
                                "pubtimeStr": "2024.07.04",
                                "puborg": "工业和信息化部 公安部 自然资源部 住房城乡建设部 交通运输部",
                                "pcode": "工信部联通装函〔2024〕181号",
                            }
                        ]
                    },
                    "otherfile": {
                        "listVO": [
                            {
                                "title": "《关于开展<em>智能</em><em>网联</em><em>汽车</em>准入和上路通行<em>试点</em>工作的<em>通知</em>》解读",
                                "url": "https://www.gov.cn/zhengce/202311/content_6915789.htm",
                                "summary": "政策解读。",
                                "pubtimeStr": "2023.11.17",
                                "puborg": None,
                                "pcode": "",
                            }
                        ]
                    },
                }
            },
        }

    monkeypatch.setattr(http_client, "fetch_json", _fake_fetch_json)

    records = asyncio.run(
        policy_registry.search_policy_registry(
            query="智能网联汽车 试点 通知",
            max_results=5,
        )
    )

    assert len(records) == 2
    assert records[0]["title"] == "五部门关于公布智能网联汽车“车路云一体化”应用试点城市名单的通知"
    assert records[0]["authority"] == "工业和信息化部 公安部 自然资源部 住房城乡建设部 交通运输部"
    assert records[0]["publication_date"] == "2024-07-04"
    assert records[0]["url"] == "https://www.gov.cn/zhengce/zhengceku/202407/content_6965771.htm"
    assert "工信部联通装函〔2024〕181号" in records[0]["snippet"]
    assert records[1]["authority"] == "State Council"


def test_policy_registry_client_retries_with_broader_search_field_when_title_search_misses(
    monkeypatch,
) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients import policy_registry

    observed_fields: list[str] = []

    async def _fake_fetch_json(**kwargs: object) -> object:
        observed_fields.append(kwargs["params"]["searchfield"])
        if kwargs["params"]["searchfield"] == "title":
            return {"code": 1001, "msg": "抱歉，没有找到相关结果", "data": []}
        return {
            "code": 200,
            "msg": "操作成功",
            "searchVO": {
                "catMap": {
                    "bumenfile": {
                        "listVO": [
                            {
                                "title": "四部委关于开展<em>智能</em><em>网联</em><em>汽车</em>准入和上路通行<em>试点</em>工作的<em>通知</em>",
                                "url": "https://www.gov.cn/zhengce/zhengceku/202311/content_6915788.htm",
                                "summary": "通过更宽的内容搜索命中。",
                                "pubtimeStr": "2023.11.17",
                                "puborg": "工业和信息化部 公安部 住房城乡建设部 交通运输部",
                                "pcode": "工信部联通装〔2023〕217号",
                            }
                        ]
                    }
                }
            },
        }

    monkeypatch.setattr(http_client, "fetch_json", _fake_fetch_json)

    records = asyncio.run(
        policy_registry.search_policy_registry(
            query="自动驾驶 试点 监管",
            max_results=5,
        )
    )

    assert observed_fields == ["title", "title:content:summary"]
    assert len(records) == 1
    assert records[0]["title"] == "四部委关于开展智能网联汽车准入和上路通行试点工作的通知"


def test_policy_registry_live_adapter_prefers_gov_policy_library_before_open_web_fallback(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _fake_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "智能网联汽车 试点 通知"
        assert max_results == 5
        return [
            {
                "title": "五部门关于开展智能网联汽车“车路云一体化”应用试点工作的通知",
                "url": "https://www.gov.cn/zhengce/zhengceku/202401/content_6926711.htm",
                "snippet": "官方政策库命中的试点工作通知。",
                "authority": "工业和信息化部 公安部 自然资源部 住房城乡建设部 交通运输部",
                "jurisdiction": "CN",
                "publication_date": "2024-01-18",
                "effective_date": None,
                "version": None,
            }
        ]

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        raise AssertionError("open web fallback should not run when gov policy library hits exist")

    monkeypatch.setattr(adapter, "search_policy_registry", _fake_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)

    hits = asyncio.run(adapter.search_live("智能网联汽车 试点 通知"))

    assert len(hits) == 1
    assert hits[0].url == "https://www.gov.cn/zhengce/zhengceku/202401/content_6926711.htm"
    assert hits[0].authority == "工业和信息化部 公安部 自然资源部 住房城乡建设部 交通运输部"
    assert hits[0].publication_date == "2024-01-18"
    assert hits[0].jurisdiction == "CN"


def test_policy_registry_live_adapter_ignores_weak_gov_hits_and_falls_back_to_open_web(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _weak_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        return [
            {
                "title": "国务院关于全国部分地区要素市场化配置综合改革试点实施方案的批复",
                "url": "https://www.gov.cn/zhengce/zhengceku/202509/content_7040122.htm",
                "snippet": "只和“试点”有弱匹配。",
                "authority": "国务院",
                "jurisdiction": "CN",
                "publication_date": "2025-09-11",
                "effective_date": None,
                "version": None,
            }
        ]

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="四部委关于开展智能网联汽车准入和上路通行试点工作的通知",
                url="https://www.gov.cn/zhengce/zhengceku/202311/content_6915788.htm",
                snippet="更强的官方相关命中。",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: Ministry of Industry and Information Technology\n"
            "Publication date: 2023-11-17\n"
            "Effective date: 2023-12-01\n"
            "Version: 2023 pilot notice\n"
            "本通知明确自动驾驶监管要求，并细化智能网联汽车准入和上路通行试点安排。"
        )

    monkeypatch.setattr(adapter, "search_policy_registry", _weak_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("自动驾驶 试点 监管"))

    assert len(hits) == 1
    assert hits[0].title == "四部委关于开展智能网联汽车准入和上路通行试点工作的通知"
    assert hits[0].effective_date == "2023-12-01"


def test_policy_registry_live_adapter_drops_weak_open_web_fallback_hits(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "自动驾驶 试点 监管"
        assert max_results == 5
        return []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="国务院关于全国部分地区要素市场化配置综合改革试点实施方案的批复",
                url="https://www.gov.cn/zhengce/zhengceku/202509/content_7040122.htm",
                snippet="只和“试点”有弱匹配。",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: State Council\n"
            "Publication date: 2025-09-11\n"
            "Effective date: 2025-10-01\n"
            "Version: 2025 reply"
        )

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("自动驾驶 试点 监管"))

    assert hits == []


def test_policy_registry_live_adapter_filters_to_official_domains_and_extracts_metadata(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="Climate Order",
                url="https://www.gov.cn/zhengce/climate-order",
                snippet="Official climate order release.",
            ),
            SearchCandidate(
                engine="bing",
                title="Climate Order analysis",
                url="https://blog.example.com/climate-order-analysis",
                snippet="Non-official policy commentary.",
            ),
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: State Council\n"
            "Publication date: 2026-04-01\n"
            "Effective date: 2026-05-01\n"
            "Version: 2026-04 edition\n"
            "Official climate order release."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("latest climate order version"))

    assert len(hits) == 1
    assert hits[0].url == "https://www.gov.cn/zhengce/climate-order"
    assert hits[0].authority == "State Council"
    assert hits[0].jurisdiction == "CN"
    assert hits[0].publication_date == "2026-04-01"
    assert hits[0].effective_date == "2026-05-01"
    assert hits[0].version == "2026-04 edition"


def test_policy_allowlist_live_adapter_rejects_non_official_domains(monkeypatch) -> None:
    import skill.retrieval.adapters.policy_official_web_allowlist as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="SAMR regulatory interpretation",
                url="https://www.samr.gov.cn/fgs/art/2026/4/11/art_1234.html",
                snippet="Regulator interpretation note.",
            ),
            SearchCandidate(
                engine="bing",
                title="Policy hot take",
                url="https://blog.example.com/policy-hot-take",
                snippet="Commentary from a blog.",
            ),
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: State Administration for Market Regulation\n"
            "Publication date: 2026-04-11\n"
            "Effective date: 2026-04-20\n"
            "Version: 2026-04-11 interpretation"
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("latest emissions regulation"))

    assert len(hits) == 1
    assert hits[0].authority == "State Administration for Market Regulation"
    assert hits[0].jurisdiction == "CN"
    assert "blog.example.com" not in hits[0].url
