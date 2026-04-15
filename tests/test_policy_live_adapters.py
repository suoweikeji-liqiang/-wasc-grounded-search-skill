"""Contracts for live policy adapter implementations."""

from __future__ import annotations

import asyncio


def test_policy_parser_accepts_fcc_and_etsi_official_domains() -> None:
    from skill.retrieval.live.parsers.policy import (
        is_official_policy_url,
        policy_domain_metadata,
    )

    assert is_official_policy_url("https://www.fcc.gov/CyberTrustMark")
    assert is_official_policy_url(
        "https://docs.fcc.gov/public/attachments/DOC-401201A1.pdf"
    )
    assert is_official_policy_url("https://www.etsi.org/technologies/consumer-iot-security")

    assert policy_domain_metadata("https://www.fcc.gov/CyberTrustMark") == (
        "Federal Communications Commission",
        "US",
    )
    assert policy_domain_metadata("https://www.etsi.org/technologies/consumer-iot-security") == (
        "European Telecommunications Standards Institute",
        "EU",
    )


def test_policy_parser_prioritizes_fcc_and_etsi_for_cyber_trust_queries() -> None:
    from skill.retrieval.live.parsers.policy import preferred_policy_domains

    domains = preferred_policy_domains(
        "FCC Cyber Trust Mark minimum security requirements eligibility scope and ETSI EN 303 645 mapping",
        fallback=False,
    )

    assert domains[:4] == ("fcc.gov", "www.fcc.gov", "docs.fcc.gov", "etsi.org")


def test_policy_parser_prioritizes_ofcom_for_illegal_harms_code_queries() -> None:
    from skill.retrieval.live.parsers.policy import preferred_policy_domains

    domains = preferred_policy_domains(
        "UK Online Safety Act Ofcom compliance milestones illegal harms codes of practice",
        fallback=False,
    )

    assert domains[:2] == ("ofcom.org.uk", "legislation.gov.uk")


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
        asyncio.wait_for(
            policy_registry.search_policy_registry(
            query="智能网联汽车 试点 通知",
            max_results=5,
            ),
            timeout=0.2,
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
    all_started = asyncio.Event()

    async def _fake_fetch_json(**kwargs: object) -> object:
        searchfield = kwargs["params"]["searchfield"]
        observed_fields.append(searchfield)
        if len(observed_fields) == 2:
            all_started.set()
        await all_started.wait()
        if searchfield == "title":
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
        asyncio.wait_for(
            policy_registry.search_policy_registry(
            query="自动驾驶 试点 监管",
            max_results=5,
            ),
            timeout=0.2,
        )
    )

    assert set(observed_fields) == {"title", "title:content:summary"}
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
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

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
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

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
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(adapter.search_live("自动驾驶 试点 监管"))

    assert hits == []


def test_policy_registry_live_adapter_filters_to_official_domains_and_extracts_metadata(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latest climate order version"
        assert max_results == 5
        return []

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
    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)

    hits = asyncio.run(adapter.search_live("latest climate order version"))

    assert len(hits) == 1
    assert hits[0].url == "https://www.gov.cn/zhengce/climate-order"
    assert hits[0].authority == "State Council"
    assert hits[0].jurisdiction == "CN"
    assert hits[0].publication_date == "2026-04-01"
    assert hits[0].effective_date == "2026-05-01"
    assert hits[0].version == "2026-04 edition"


def test_policy_registry_live_adapter_keeps_strong_official_candidate_when_page_fetch_is_empty(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "NIS2 Directive transposition deadline adopt publish national measures official text"
        assert max_results == 5
        return []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Directive (EU) 2022/2555 on measures for a high common level of cybersecurity across the Union",
                url="https://eur-lex.europa.eu/eli/dir/2022/2555/oj",
                snippet="Official directive text published 2022-12-27 with Member State transposition deadline 2024-10-17.",
            )
        ]

    async def _empty_fetch_page_text(**_: object) -> str:
        return ""

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _empty_fetch_page_text)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        adapter.search_live(
            "NIS2 Directive transposition deadline adopt publish national measures official text"
        )
    )

    assert len(hits) == 1
    assert hits[0].url.startswith("https://eur-lex.europa.eu/eli/dir/2022/2555/")
    assert hits[0].authority == "European Union"
    assert hits[0].jurisdiction == "EU"


def test_policy_registry_live_adapter_starts_open_web_fallback_while_registry_is_in_flight(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    started: list[str] = []
    all_started = asyncio.Event()

    async def _slow_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latest climate order version"
        assert max_results == 5
        started.append("registry")
        if len(started) == 2:
            all_started.set()
        await all_started.wait()
        return []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        started.append("fallback")
        if len(started) == 2:
            all_started.set()
        await all_started.wait()
        return [
            SearchCandidate(
                engine="bing",
                title="Climate Order",
                url="https://www.gov.cn/zhengce/climate-order",
                snippet="Official climate order release.",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: State Council\n"
            "Publication date: 2026-04-01\n"
            "Effective date: 2026-05-01\n"
            "Version: 2026-04 edition\n"
            "Official climate order release."
        )

    monkeypatch.setattr(adapter, "search_policy_registry", _slow_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)
    monkeypatch.setattr(adapter, "preferred_policy_domains", lambda query, *, fallback: ("gov.cn",))

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live("latest climate order version"),
            timeout=0.2,
        )
    )

    assert started == ["registry", "fallback"]
    assert len(hits) == 1
    assert hits[0].url == "https://www.gov.cn/zhengce/climate-order"


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


def test_policy_allowlist_live_adapter_uses_fact_dense_page_paragraphs_when_intro_is_long(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_web_allowlist as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Climate Order",
                url="https://www.gov.cn/zhengce/climate-order",
                snippet="",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "This climate order page provides general background on national coordination, "
            "institutional alignment, implementation framing, and long-term planning context "
            "for agencies and supervised entities across multiple sectors.\n\n"
            "The introductory overview explains why the policy matters, how it fits within the "
            "broader strategy, and what kinds of implementation questions regulated parties "
            "should expect over time as additional guidance is issued.\n\n"
            "Authority: State Council. Publication date: 2026-04-01. Effective date: 2026-05-01. "
            "Version: 2026-04 edition. Article 12 requires quarterly methane reporting.\n\n"
            "Archive and navigation links."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("latest climate order version article 12 effective date"))

    assert len(hits) == 1
    assert "Effective date: 2026-05-01" in hits[0].snippet
    assert "Version: 2026-04 edition" in hits[0].snippet
    assert "Article 12 requires quarterly methane reporting" in hits[0].snippet


def test_policy_allowlist_live_adapter_replaces_generic_search_snippet_with_fact_dense_page_text(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_web_allowlist as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="Climate Order",
                url="https://www.gov.cn/zhengce/climate-order",
                snippet="Official climate order release and overview.",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Official climate order release page.\n\n"
            "Authority: State Council. Publication date: 2026-04-01. Effective date: 2026-05-01. "
            "Version: 2026-04 edition. Article 12 requires quarterly methane reporting and "
            "Article 15 defines the compliance record format.\n\n"
            "Supplementary contact information."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("latest climate order effective date version"))

    assert len(hits) == 1
    assert hits[0].snippet != "Official climate order release and overview."
    assert "Effective date: 2026-05-01" in hits[0].snippet
    assert "Article 15 defines the compliance record format" in hits[0].snippet


def test_policy_registry_live_adapter_uses_federal_register_for_us_official_queries(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latest EPA methane rule effective date"
        assert max_results == 5
        return []

    async def _fake_search_federal_register(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latest EPA methane rule effective date"
        assert max_results == 5
        return [
            {
                "title": "Oil and Natural Gas Sector: Reduction of Methane Emissions",
                "url": "https://www.federalregister.gov/documents/2026/04/11/2026-00001/methane-rule",
                "snippet": "Official Federal Register rule notice.",
                "authority": "Environmental Protection Agency",
                "jurisdiction": "US",
                "publication_date": "2026-04-11",
                "effective_date": "2026-05-11",
                "version": "2026 final rule",
            }
        ]

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        raise AssertionError("open web fallback should not run when Federal Register hits exist")

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_federal_register", _fake_search_federal_register)
    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)

    hits = asyncio.run(adapter.search_live("latest EPA methane rule effective date"))

    assert len(hits) == 1
    assert hits[0].authority == "Environmental Protection Agency"
    assert hits[0].jurisdiction == "US"
    assert hits[0].publication_date == "2026-04-11"
    assert hits[0].effective_date == "2026-05-11"
    assert hits[0].version == "2026 final rule"


def test_policy_allowlist_live_adapter_accepts_npc_law_database_domains(monkeypatch) -> None:
    import skill.retrieval.adapters.policy_official_web_allowlist as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="中华人民共和国公司法",
                url="https://flk.npc.gov.cn/detail2.html?ZmY4MDgxODE3NTJiNjQ0MzAxNzYzNzA0NTg4MjU3",
                snippet="国家法律法规数据库正式文本。",
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Authority: National People's Congress\n"
            "Publication date: 2023-12-29\n"
            "Effective date: 2024-07-01\n"
            "Version: 2023 revised edition\n"
            "国家法律法规数据库正式发布文本。"
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("公司法 修订 生效 日期"))

    assert len(hits) == 1
    assert hits[0].url.startswith("https://flk.npc.gov.cn/")
    assert hits[0].authority == "National People's Congress"
    assert hits[0].jurisdiction == "CN"


def test_policy_registry_live_adapter_uses_pruned_policy_search_fanout(monkeypatch) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    search_calls: list[tuple[str, tuple[str, ...]]] = []

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latest climate order version"
        assert max_results == 5
        return []

    async def _fake_search_multi_engine(**kwargs: object) -> list[object]:
        search_calls.append((kwargs["query"], kwargs["engines"]))
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)

    hits = asyncio.run(adapter.search_live("latest climate order version"))

    assert len(hits) <= 5
    assert search_calls
    assert len(search_calls) <= 3
    assert all("google" not in engines for _, engines in search_calls)


def test_policy_registry_live_adapter_falls_back_to_ranked_fixture_hits_when_live_search_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "AI chip export controls 对 academic research 影响"
        assert max_results == 5
        return []

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)

    hits = asyncio.run(adapter.search_live("AI chip export controls 对 academic research 影响"))

    assert hits
    assert hits[0].url == "https://www.mofcom.gov.cn/article/ai-chip-export-controls-2026"
