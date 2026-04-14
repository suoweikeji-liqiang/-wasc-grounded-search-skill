"""Contracts for live policy adapter implementations."""

from __future__ import annotations

import asyncio


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
