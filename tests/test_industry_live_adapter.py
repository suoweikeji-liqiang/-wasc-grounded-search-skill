"""Contracts for the live industry adapter."""

from __future__ import annotations

import asyncio


def test_industry_live_adapter_aggregates_candidates_and_assigns_tiers(monkeypatch) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="Tesla annual battery supply update",
                url="https://www.tesla.com/blog/battery-supply-update",
                snippet="Company update on battery production guidance.",
            ),
            SearchCandidate(
                engine="bing",
                title="SEMI outlook for semiconductor packaging capacity",
                url="https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
                snippet="Association forecast for semiconductor packaging capacity.",
            ),
            SearchCandidate(
                engine="google",
                title="Battery recycling market share outlook",
                url="https://www.reuters.com/markets/battery-recycling-share-2025",
                snippet="Trusted news outlook for battery recycling market share.",
            ),
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("battery recycling market share 2025"))

    assert len(hits) == 3
    assert {hit.credibility_tier for hit in hits} == {
        "company_official",
        "industry_association",
        "trusted_news",
    }


def test_industry_live_adapter_prefers_exact_query_match_over_generic_company_update(monkeypatch) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="Tesla annual battery supply update",
                url="https://www.tesla.com/blog/battery-supply-update",
                snippet="Generic company update on battery production guidance.",
            ),
            SearchCandidate(
                engine="bing",
                title="SEMI outlook for semiconductor packaging capacity",
                url="https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
                snippet="Association forecast for semiconductor packaging capacity in 2026.",
            ),
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("semiconductor packaging capacity forecast 2026"))

    assert hits[0].title == "SEMI outlook for semiconductor packaging capacity"
    assert hits[0].credibility_tier == "industry_association"


def test_industry_live_adapter_retains_relevant_company_official_hit(monkeypatch) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="duckduckgo",
                title="Trusted battery recycling market report",
                url="https://www.reuters.com/markets/battery-recycling-share-2025",
                snippet="Trusted news report focused on battery recycling market share.",
            ),
            SearchCandidate(
                engine="bing",
                title="Battery recycling trade association outlook",
                url="https://www.semi.org/en/news-resources/market-data/battery-recycling-2025",
                snippet="Industry association outlook on battery recycling.",
            ),
            SearchCandidate(
                engine="google",
                title="General market commentary",
                url="https://example.com/battery-recycling-commentary",
                snippet="General commentary on the battery market.",
            ),
            SearchCandidate(
                engine="google",
                title="Tesla battery recycling supplier update",
                url="https://www.tesla.com/blog/battery-recycling-supplier-update",
                snippet="Company official update on battery recycling suppliers.",
            ),
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("battery recycling market share 2025"))

    assert len(hits) == 3
    assert "company_official" in {hit.credibility_tier for hit in hits}
    assert any("Tesla" in hit.title for hit in hits)
