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


def test_industry_live_adapter_replaces_generic_search_snippet_with_fact_dense_page_excerpt(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    candidate_snippet = "General outlook for advanced packaging capacity in 2026."

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="SEMI advanced packaging outlook",
                url="https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
                snippet=candidate_snippet,
            )
        ]

    async def _fake_fetch_page_text(**_: object) -> str:
        return (
            "This update reviews the advanced packaging ecosystem, vendor positioning, and the "
            "broader outlook for advanced packaging capacity in 2026 across major supply chains.\n\n"
            "SEMI said advanced packaging capacity reached 385,000 wafers per month in 2026, "
            "up 18% year over year, while CoWoS capacity share rose to 62%."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)

    hits = asyncio.run(adapter.search_live("advanced packaging capacity outlook 2026"))

    assert len(hits) == 1
    assert hits[0].snippet != candidate_snippet
    assert "385,000 wafers per month" in hits[0].snippet
    assert "18% year over year" in hits[0].snippet


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


def test_industry_live_adapter_uses_google_news_rss_when_open_web_discovery_is_empty(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    observed_engine_calls: list[tuple[str, ...]] = []

    async def _fake_search_multi_engine(**kwargs: object) -> list[SearchCandidate]:
        engines = tuple(kwargs["engines"])
        observed_engine_calls.append(engines)
        if engines == ("duckduckgo", "bing", "google"):
            return []
        if engines == ("google_news_rss",):
            return [
                SearchCandidate(
                    engine="google_news_rss",
                    title="Battery Recycling Global Markets Report 2025-2030 - Yahoo Finance",
                    url="https://news.google.com/rss/articles/example-1",
                    snippet="Yahoo Finance. Tue, 04 Feb 2025 08:00:00 GMT",
                    source_url="https://finance.yahoo.com",
                )
            ]
        return []

    async def _empty_search_sec_filings(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_search_sec_company_submissions(**_: object) -> list[dict[str, object]]:
        return []

    async def _unexpected_fetch_page_text(**_: object) -> str:
        raise AssertionError("google_news_rss fallback should not fetch source pages directly")

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _empty_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _empty_search_sec_company_submissions,
    )
    monkeypatch.setattr(adapter, "fetch_page_text", _unexpected_fetch_page_text)

    hits = asyncio.run(adapter.search_live("battery recycling market share 2025"))

    assert len(hits) == 1
    assert hits[0].url == "https://news.google.com/rss/articles/example-1"
    assert "Yahoo Finance" in hits[0].snippet
    assert observed_engine_calls == [
        ("duckduckgo", "bing", "google"),
        ("google_news_rss",),
    ]


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

    async def _empty_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        url = str(kwargs["url"])
        if "sec.gov" in url:
            return (
                "Tesla annual report discusses battery supply, production capacity, and guidance."
            )
        return "Trusted news commentary on Tesla battery production."

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _empty_search_sec_company_submissions,
    )
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

    async def _empty_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        fetched_urls.append(str(kwargs["url"]))
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _empty_search_sec_company_submissions,
    )
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


def test_industry_live_adapter_returns_sec_hits_without_waiting_for_slow_web_search(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _slow_search_multi_engine(**_: object) -> list[object]:
        await asyncio.sleep(10)
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

    async def _empty_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _unexpected_fetch_page_text(**_: object) -> str:
        raise AssertionError("strong SEC hit should return without page fetch")

    monkeypatch.setattr(adapter, "search_multi_engine", _slow_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _empty_search_sec_company_submissions,
    )
    monkeypatch.setattr(adapter, "fetch_page_text", _unexpected_fetch_page_text)

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "NVIDIA fiscal 2026 Form 10-K risk factors supply chain export controls"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "NVIDIA Corporation Form 10-K filing"


def test_industry_live_adapter_generic_company_filing_path_uses_fastest_sec_hit(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        raise AssertionError("generic SEC hit should not fall through to generic search")

    async def _fast_search_sec_filings(
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

    async def _slow_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        await asyncio.sleep(10)
        return []

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == "https://www.sec.gov/Archives/edgar/data/1318605/000110465925042659/tsla-20241231x10k.htm"
        return "Tesla annual report discusses battery supply, production capacity, and guidance."

    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fast_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _slow_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        asyncio.wait_for(adapter.search_live("Tesla 10-K battery supply guidance"), timeout=1.5)
    )

    assert len(hits) == 1
    assert hits[0].title == "Tesla, Inc. Form 10-K filing"
    assert "battery supply" in hits[0].snippet.lower()


def test_industry_live_adapter_uses_company_submission_fallback_when_sec_search_times_out(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _timed_out_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == (
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
        assert max_results == 3
        raise TimeoutError

    async def _fake_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == (
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
        assert max_results == 3
        return [
            {
                "title": "Microsoft Corporation Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025118440/msft-20250630.htm",
                "snippet": "Official SEC filing for Microsoft annual report.",
                "credibility_tier": "company_official",
            }
        ]

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == "https://www.sec.gov/Archives/edgar/data/789019/000095017025118440/msft-20250630.htm"
        return (
            "Microsoft reports revenue in three segments: Productivity and Business Processes, "
            "Intelligent Cloud, and More Personal Computing."
        )

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_query_aligned_page_text(**_: object) -> str:
        return "CET1 ratio and Basel III endgame discussion remain central capital topics."

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _timed_out_search_sec_filings)
    monkeypatch.setattr(adapter, "search_sec_company_submissions", _fake_search_sec_company_submissions)
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live(
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "Microsoft Corporation Form 10-K filing"
    assert "Intelligent Cloud" in hits[0].snippet


def test_industry_live_adapter_prefers_fast_company_submissions_over_slow_sec_search(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _slow_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Boeing 2025 Form 10-K backlog definition order cancellation policy"
        assert max_results == 3
        await asyncio.sleep(10)
        return []

    async def _fast_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Boeing 2025 Form 10-K backlog definition order cancellation policy"
        assert max_results == 3
        return [
            {
                "title": "BOEING CO Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm",
                "snippet": "Official SEC filing 10-K filed 2026-01-30 report period 2025-12-31",
                "credibility_tier": "company_official",
            }
        ]

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == "https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm"
        return "Backlog includes contractual orders and reflects cancellation exposure."

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _slow_search_sec_filings)
    monkeypatch.setattr(adapter, "search_sec_company_submissions", _fast_search_sec_company_submissions)
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live("Boeing 2025 Form 10-K backlog definition order cancellation policy"),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "BOEING CO Form 10-K filing"
    assert "backlog" in hits[0].snippet.lower()
    assert "cancellation" in hits[0].snippet.lower()


def test_industry_live_adapter_enriches_weak_official_filing_hits_with_page_excerpt(
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
        assert query == (
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
        assert max_results == 3
        return [
            {
                "title": "Microsoft Corporation Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025118440/msft-20250630.htm",
                "snippet": "Official SEC filing for Microsoft annual report.",
                "credibility_tier": "company_official",
            }
        ]

    async def _empty_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        fetched_urls.append(str(kwargs["url"]))
        return (
            "Microsoft reports revenue in three segments: Productivity and Business Processes, "
            "Intelligent Cloud, and More Personal Computing."
        )

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fake_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _empty_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live(
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "Microsoft Corporation Form 10-K filing"
    assert "Intelligent Cloud" in hits[0].snippet
    assert any("sec.gov" in url for url in fetched_urls)


def test_industry_live_adapter_keeps_query_aligned_sec_excerpt_when_metadata_scores_higher(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _unexpected_search_sec_filings(**_: object) -> list[dict[str, object]]:
        raise AssertionError("Ford known-company path should resolve via company submissions")

    async def _fake_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Ford 2025 Form 10-K warranty accrual accounting policy changes"
        assert max_results == 3
        return [
            {
                "title": "FORD MOTOR CO Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/37996/000003799626000015/f-20251231.htm",
                "snippet": "Official SEC filing 10-K filed 2026-02-11 report period 2025-12-31",
                "credibility_tier": "company_official",
            }
        ]

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_fetch_query_aligned_page_text(**_: object) -> str:
        return (
            "For additional information regarding warranty and field service action costs, "
            "including our process for establishing our reserves, see Critical Accounting Estimates."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _unexpected_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fake_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live("Ford 2025 Form 10-K warranty accrual accounting policy changes")
    )

    assert len(hits) == 1
    assert hits[0].title == "FORD MOTOR CO Form 10-K filing"
    assert "warranty" in hits[0].snippet.lower()
    assert "critical accounting estimates" in hits[0].snippet.lower()
    assert "official sec filing" not in hits[0].snippet.lower()


def test_industry_live_adapter_limits_early_sec_excerpt_fetch_to_top_record(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed_urls: list[str] = []

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        raise AssertionError("early SEC hit should not fall through to generic search")

    async def _empty_search_sec_filings(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _fake_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Microsoft FY2026 Form 10-K remaining performance obligations definition"
        assert max_results == 3
        return [
            {
                "title": "MICROSOFT CORP Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
                "snippet": "Official SEC filing 10-K filed 2025-07-30 report period 2025-06-30",
                "credibility_tier": "company_official",
            },
            {
                "title": "MICROSOFT CORP Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/msft-20240630.htm",
                "snippet": "Official SEC filing 10-K filed 2024-07-30 report period 2024-06-30",
                "credibility_tier": "company_official",
            },
            {
                "title": "MICROSOFT CORP Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000156459023033093/msft-10k_20230630.htm",
                "snippet": "Official SEC filing 10-K filed 2023-07-27 report period 2023-06-30",
                "credibility_tier": "company_official",
            },
        ]

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        observed_urls.append(str(kwargs["url"]))
        return (
            "Revenue allocated to remaining performance obligations includes unearned revenue "
            "and amounts to be invoiced and recognized in future periods."
        )

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _empty_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fake_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live("Microsoft FY2026 Form 10-K remaining performance obligations definition")
    )

    assert len(hits) == 1
    assert hits[0].title == "MICROSOFT CORP Form 10-K filing"
    assert observed_urls == [
        "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm"
    ]


def test_industry_live_adapter_refetches_sec_archive_when_initial_excerpt_lacks_focus_terms(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed_limits: list[int] = []

    async def _fake_fetch_text_limited(
        *,
        url: str,
        timeout: float = 10.0,
        max_chars: int = 0,
        **_: object,
    ) -> str:
        assert "sec.gov" in url
        assert timeout <= 4.0
        observed_limits.append(max_chars)
        if max_chars < 900_000:
            return "<html><body>initial-pass</body></html>"
        return "<html><body>deep-pass</body></html>"

    def _fake_extract_query_aligned_page_excerpt(
        *,
        html: str,
        query: str,
        title: str,
        candidate_snippet: str,
        max_chars: int = 320,
    ) -> str:
        assert query == "Boeing 2025 Form 10-K backlog definition order cancellation policy"
        assert title == "BOEING CO Form 10-K filing"
        assert max_chars == 260
        if "initial-pass" in html:
            return (
                "Our contractual backlog consists of aircraft scheduled for delivery "
                "over a period of several years."
            )
        return (
            "Backlog increased in 2025, reflecting new orders in excess of deliveries, "
            "partially offset by cancellations."
        )

    monkeypatch.setattr(adapter.http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(
        adapter,
        "extract_query_aligned_page_excerpt",
        _fake_extract_query_aligned_page_excerpt,
    )

    excerpt = asyncio.run(
        adapter._fetch_query_aligned_page_text(
            query="Boeing 2025 Form 10-K backlog definition order cancellation policy",
            title="BOEING CO Form 10-K filing",
            url="https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm",
            candidate_snippet="Official SEC filing 10-K filed 2026-01-30 report period 2025-12-31",
        )
    )

    assert observed_limits == [650_000, 900_000]
    assert "cancellations" in excerpt.lower()


def test_industry_live_adapter_uses_query_aligned_sec_excerpt_for_boeing_backlog_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _unexpected_search_sec_filings(**_: object) -> list[dict[str, object]]:
        raise AssertionError("Boeing known-company path should resolve via company submissions")

    async def _fake_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Boeing 2025 Form 10-K backlog definition order cancellation policy"
        assert max_results == 3
        return [
            {
                "title": "BOEING CO Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm",
                "snippet": "Official SEC filing 10-K filed 2026-01-30 report period 2025-12-31",
                "credibility_tier": "company_official",
            }
        ]

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_fetch_query_aligned_page_text(**_: object) -> str:
        return (
            "our contractual backlog. In addition, because our commercial aircraft backlog "
            "consists of aircraft scheduled for delivery over a period of several years, any "
            "of these macroeconomic, industry or customer impacts could affect deliveries over "
            "a long period. We enter into firm fixed-price aircraft sales contracts with indexed "
            "price escalation clauses, which subjects us to losses if we have cost overruns or "
            "if increases in our costs exceed the applicable escalation rate. Commercial aircraft "
            "sales contracts are typically entered into years before the aircraft are delivered. "
            "In order to help account"
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _unexpected_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fake_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live("Boeing 2025 Form 10-K backlog definition order cancellation policy")
    )

    assert len(hits) == 1
    assert hits[0].title == "BOEING CO Form 10-K filing"
    assert "backlog" in hits[0].snippet.lower()
    assert "official sec filing" not in hits[0].snippet.lower()
    assert len(hits[0].snippet.split()) <= 40


def test_industry_live_adapter_uses_direct_rfc_official_candidate_when_discovery_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    fetched_urls: list[str] = []

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        fetched_urls.append(str(kwargs["url"]))
        return (
            "RFC 9700 specifies OAuth 2.1. The specification removes the implicit grant and "
            "resource owner password credentials grant and consolidates security guidance."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live(
            "RFC 9700 OAuth 2.1 legacy authorization flows grant types removed discouraged sections"
        )
    )

    assert len(hits) >= 1
    assert hits[0].url == "https://datatracker.ietf.org/doc/html/rfc9700"
    assert hits[0].credibility_tier == "industry_association"
    assert "implicit grant" in hits[0].snippet.lower()
    assert len(hits[0].snippet.split()) <= 40
    assert fetched_urls == ["https://datatracker.ietf.org/doc/html/rfc9700"]


def test_industry_live_adapter_returns_direct_rfc_candidate_without_waiting_for_slow_web_search(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _slow_search_multi_engine(**_: object) -> list[object]:
        await asyncio.sleep(10)
        return []

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == "https://datatracker.ietf.org/doc/html/rfc9700"
        return (
            "RFC 9700 specifies OAuth 2.1. The specification removes the implicit grant and "
            "resource owner password credentials grant."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _slow_search_multi_engine)
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "RFC 9700 OAuth 2.1 legacy authorization flows grant types removed discouraged sections"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].url == "https://datatracker.ietf.org/doc/html/rfc9700"
    assert "implicit grant" in hits[0].snippet.lower()


def test_industry_live_adapter_sec_detection_requires_real_sec_signal() -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    assert (
        adapter._should_query_sec(
            "RFC 9700 OAuth 2.1 legacy authorization flows grant types removed discouraged sections"
        )
        is False
    )
    assert (
        adapter._should_query_sec(
            "SEC cybersecurity disclosure rules Form 8-K Item 1.05 timing annual disclosure expectations"
        )
        is True
    )


@pytest.mark.parametrize(
    ("query", "expected_url", "page_excerpt"),
    [
        (
            "W3C WebAuthn Level 3 normative term for passkey discoverable credential residentKey required implication",
            "https://www.w3.org/TR/webauthn-3/",
            "The residentKey option becomes a required member whose value guides discoverable credential behavior.",
        ),
        (
            "Chromium CHIPS cookie attribute name requests partitioning Set-Cookie token string official",
            "https://developer.chrome.com/blog/chrome-114-beta/",
            "The CHIPS cookie attribute uses the Partitioned Set-Cookie attribute to request partitioned storage.",
        ),
        (
            "中文 IETF HTTP Message Signatures Signature-Input ABNF 组件标识符 参数 规则名 小节",
            "https://datatracker.ietf.org/doc/html/rfc9421",
            "The Signature-Input field is defined in the HTTP Message Signatures specification with ABNF-based components and parameters.",
        ),
    ],
)
def test_industry_live_adapter_returns_direct_standard_alias_candidates_without_waiting_for_slow_web_search(
    monkeypatch,
    query: str,
    expected_url: str,
    page_excerpt: str,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _slow_search_multi_engine(**_: object) -> list[object]:
        await asyncio.sleep(10)
        return []

    async def _fake_fetch_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == expected_url
        return page_excerpt

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == expected_url
        return page_excerpt

    monkeypatch.setattr(adapter, "search_multi_engine", _slow_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _fake_fetch_page_text)
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(asyncio.wait_for(adapter.search_live(query), timeout=1.0))

    assert len(hits) == 1
    assert hits[0].url == expected_url
    assert hits[0].credibility_tier == "industry_association"
    assert page_excerpt.split()[0].lower() in hits[0].snippet.lower()


def test_industry_live_adapter_known_company_filing_path_skips_generic_search_when_company_submissions_hit(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed = {
        "web_search_called": False,
        "sec_search_called": False,
    }

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        observed["web_search_called"] = True
        return []

    async def _unexpected_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        observed["sec_search_called"] = True
        return []

    async def _fast_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == (
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
        assert max_results == 3
        return [
            {
                "title": "Microsoft Corporation Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025118440/msft-20250630.htm",
                "snippet": (
                    "Official SEC filing 10-K filed 2025-07-30 report period 2025-06-30 "
                    "Intelligent Cloud Productivity More Personal Computing."
                ),
                "credibility_tier": "company_official",
            }
        ]

    async def _unexpected_fetch_page_text(**_: object) -> str:
        raise AssertionError("strong company submissions hit should return without page fetch")

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_query_aligned_page_text(**_: object) -> str:
        return "CET1 ratio and Basel III endgame discussion remain central capital topics."

    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _unexpected_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fast_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(adapter, "fetch_page_text", _unexpected_fetch_page_text)

    hits = asyncio.run(
        adapter.search_live(
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "Microsoft Corporation Form 10-K filing"
    assert observed["web_search_called"] is False
    assert observed["sec_search_called"] is False


def test_industry_live_adapter_falls_back_to_sec_search_when_company_submissions_timeout(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed = {
        "web_search_called": False,
        "sec_search_called": False,
    }

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        observed["web_search_called"] = True
        return []

    async def _fallback_search_sec_filings(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        observed["sec_search_called"] = True
        assert query == "JPMorgan Chase 2025 Form 10-K CET1 ratio Basel III endgame discussion"
        assert max_results == 3
        return [
            {
                "title": "JPMORGAN CHASE & CO Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/19617/000001961726000097/jpm-20251231.htm",
                "snippet": (
                    "Official SEC filing 10-K filed 2026-02-24 report period 2025-12-31 "
                    "CET1 Basel III endgame discussion."
                ),
                "credibility_tier": "company_official",
            }
        ]

    async def _timed_out_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        raise TimeoutError

    async def _empty_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        return []

    async def _fake_query_aligned_page_text(**_: object) -> str:
        return "CET1 ratio and Basel III endgame discussion remain central capital topics."

    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _fallback_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _timed_out_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _empty_company_ir_candidates,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live(
            "JPMorgan Chase 2025 Form 10-K CET1 ratio Basel III endgame discussion"
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "JPMORGAN CHASE & CO Form 10-K filing"
    assert observed["web_search_called"] is False
    assert observed["sec_search_called"] is True


def test_industry_live_adapter_prefers_query_aligned_company_ir_page_before_sec_metadata(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed = {
        "web_search_called": False,
        "sec_search_called": False,
        "company_submissions_called": False,
    }

    homepage_url = "https://www.microsoft.com/en-us/Investor"
    segment_url = (
        "https://www.microsoft.com/en-us/Investor/earnings/"
        "FY-2026-Q2/productivity-and-business-processes-performance"
    )

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        observed["web_search_called"] = True
        return []

    async def _unexpected_search_sec_filings(**_: object) -> list[dict[str, object]]:
        observed["sec_search_called"] = True
        return []

    async def _unexpected_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        observed["company_submissions_called"] = True
        return []

    async def _fake_fetch_text(
        *,
        url: str,
        timeout: float = 10.0,
        **_: object,
    ) -> str:
        assert timeout <= 2.0
        if url == homepage_url:
            return f"""
            <html>
              <body>
                <a href="{segment_url}">Segment Performance</a>
                <a href="https://www.microsoft.com/en-us/Investor/annual-reports">Annual Reports</a>
              </body>
            </html>
            """
        if url == segment_url:
            return """
            <html>
              <head><title>FY26 Q2 - Productivity and Business Processes Performance</title></head>
              <body>
                <main>
                  Productivity and Business Processes
                  Intelligent Cloud
                  More Personal Computing
                  Segment revenue tables and performance discussion.
                </main>
              </body>
            </html>
            """
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _unexpected_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _unexpected_search_sec_company_submissions,
    )
    monkeypatch.setattr(adapter.http_client, "fetch_text", _fake_fetch_text)

    hits = asyncio.run(
        adapter.search_live(
            "Microsoft FY2025 Form 10-K segment revenue definitions "
            "Intelligent Cloud Productivity More Personal Computing"
        )
    )

    assert len(hits) >= 1
    assert hits[0].url == segment_url
    assert "Intelligent Cloud" in hits[0].snippet
    assert observed["web_search_called"] is False
    assert observed["sec_search_called"] is False
    assert observed["company_submissions_called"] is False


def test_industry_live_adapter_does_not_probe_company_ir_for_performance_obligations_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _unexpected_company_ir_candidates(**_: object) -> list[dict[str, str]]:
        raise AssertionError("performance obligations query should not trigger company IR probing")

    async def _unexpected_search_multi_engine(**_: object) -> list[object]:
        raise AssertionError("fast SEC hit should not fall through to generic search")

    async def _unexpected_search_sec_filings(**_: object) -> list[dict[str, object]]:
        raise AssertionError("known company path should resolve via company submissions first")

    async def _fast_search_sec_company_submissions(
        *,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, object]]:
        assert query == "Microsoft FY2026 Form 10-K remaining performance obligations definition"
        assert max_results == 3
        return [
            {
                "title": "MICROSOFT CORP Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
                "snippet": "Official SEC filing 10-K filed 2025-07-30 report period 2025-06-30",
                "credibility_tier": "company_official",
            }
        ]

    async def _fake_fetch_query_aligned_page_text(**kwargs: object) -> str:
        assert kwargs["url"] == "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm"
        return (
            "Revenue allocated to remaining performance obligations includes unearned revenue "
            "and amounts to be invoiced and recognized in future periods."
        )

    monkeypatch.setattr(
        adapter,
        "_search_known_company_ir_page_candidates",
        _unexpected_company_ir_candidates,
    )
    monkeypatch.setattr(adapter, "search_multi_engine", _unexpected_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _unexpected_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fast_search_sec_company_submissions,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_fetch_query_aligned_page_text,
    )

    hits = asyncio.run(
        adapter.search_live("Microsoft FY2026 Form 10-K remaining performance obligations definition")
    )

    assert len(hits) == 1
    assert hits[0].title == "MICROSOFT CORP Form 10-K filing"
    assert "remaining performance obligations" in hits[0].snippet.lower()


def test_industry_live_adapter_does_not_probe_company_ir_for_non_segment_filing_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed = {
        "company_ir_fetch_called": False,
    }

    async def _empty_search_multi_engine(**_: object) -> list[object]:
        return []

    async def _slow_search_sec_filings(**_: object) -> list[dict[str, object]]:
        await asyncio.sleep(10)
        return []

    async def _fast_search_sec_company_submissions(
        **_: object,
    ) -> list[dict[str, object]]:
        return [
            {
                "title": "BOEING CO Form 10-K filing",
                "url": "https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm",
                "snippet": "Official SEC filing 10-K filed 2026-01-30 report period 2025-12-31",
                "credibility_tier": "company_official",
            }
        ]

    async def _unexpected_company_ir_fetch(
        *,
        url: str,
        timeout: float = 10.0,
        **_: object,
    ) -> str:
        observed["company_ir_fetch_called"] = True
        raise AssertionError(f"company IR fetch should not run for backlog query: {url} {timeout}")

    async def _fake_query_aligned_page_text(**_: object) -> str:
        return "Backlog includes contractual orders and can be reduced by cancellations."

    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine)
    monkeypatch.setattr(adapter, "search_sec_filings", _slow_search_sec_filings)
    monkeypatch.setattr(
        adapter,
        "search_sec_company_submissions",
        _fast_search_sec_company_submissions,
    )
    monkeypatch.setattr(adapter.http_client, "fetch_text", _unexpected_company_ir_fetch)
    monkeypatch.setattr(
        adapter,
        "_fetch_query_aligned_page_text",
        _fake_query_aligned_page_text,
    )

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "Boeing 2025 Form 10-K backlog definition order cancellation policy"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].title == "BOEING CO Form 10-K filing"
    assert observed["company_ir_fetch_called"] is False
