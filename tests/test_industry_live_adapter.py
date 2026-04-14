"""Contracts for the live industry adapter."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _disable_fixture_shortcuts(monkeypatch) -> None:
    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "0")


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


def test_industry_live_adapter_keeps_relevant_candidate_snippet_when_page_text_is_boilerplate(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    candidate_snippet = "Trusted news report focused on battery recycling market share in 2025."

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Battery recycling market report",
                url="https://www.reuters.com/markets/battery-recycling-share-2025",
                snippet=candidate_snippet,
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "Home Markets Technology Energy Companies About Reuters Contact Privacy Terms "
            "Navigation Footer Trending Latest News Video Podcasts Newsletters Sign In Subscribe"
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("battery recycling market share 2025"))

    assert len(hits) == 1
    assert hits[0].snippet == candidate_snippet


def test_industry_live_adapter_extracts_deep_relevant_page_excerpt_for_ranking(
    monkeypatch,
) -> None:
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
                title="SEMI market data update",
                url="https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
                snippet="General market data page.",
            ),
        ]

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        url = str(kwargs["url"])
        if "tesla.com" in url:
            return "Company update on battery production guidance and manufacturing efficiency."
        return (
            ("Navigation menu latest news events membership resources " * 30)
            + "Industry association forecast for semiconductor packaging capacity in 2026 "
            + "shows continued tight supply across advanced packaging lines."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("semiconductor packaging capacity forecast 2026"))

    assert len(hits) >= 1
    assert hits[0].title == "SEMI market data update"
    assert "semiconductor packaging capacity" in hits[0].snippet.lower()


def test_industry_live_adapter_merges_official_sec_filings_for_company_filing_queries(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Tesla battery production commentary",
                url="https://www.reuters.com/markets/tesla-battery-production-commentary",
                snippet="Trusted news commentary on Tesla battery production.",
            )
        ]

    async def _fake_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Tesla 10-K battery supply guidance"
        assert max_results == 3
        return [
            {
                "title": "Tesla, Inc. Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/1318605/000110465925042659/tsla-20241231x10k.htm",
                "snippet": "Official SEC filing for Tesla annual report and business guidance.",
                "credibility_tier": "company_official",
            }
        ]

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        url = str(kwargs["url"])
        if "sec.gov" in url:
            return (
                "Tesla annual report discusses battery supply, production capacity, and guidance."
            )
        return "Trusted news commentary on Tesla battery production."

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("Tesla 10-K battery supply guidance"))

    assert len(hits) >= 1
    assert hits[0].title == "Tesla, Inc. Form 10-K filing"
    assert hits[0].credibility_tier == "company_official"
    assert hits[0].url.startswith("https://www.sec.gov/")


def test_industry_live_adapter_uses_structured_sec_hits_without_fetching_sec_pages(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    fetched_urls: list[str] = []

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _fake_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "NVIDIA fiscal 2026 Form 10-K risk factors supply chain export controls"
        assert max_results == 3
        return [
            {
                "title": "NVIDIA Corporation Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000010/nvda-20260131x10k.htm",
                "snippet": "Official SEC filing discussing supply chain and export control risk factors.",
                "credibility_tier": "company_official",
            }
        ]

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        fetched_urls.append(str(kwargs["url"]))
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(
        adapter.search_live(
            "NVIDIA fiscal 2026 Form 10-K risk factors supply chain export controls"
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "NVIDIA Corporation Form 10-K filing"
    assert hits[0].credibility_tier == "company_official"
    assert all("sec.gov" not in url for url in fetched_urls)
