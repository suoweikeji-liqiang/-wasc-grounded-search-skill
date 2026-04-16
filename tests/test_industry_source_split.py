"""Regressions for observable split industry retrieval sources."""

from __future__ import annotations

import asyncio

import pytest

from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.live.clients.search_discovery import SearchCandidate
from skill.retrieval.orchestrate import execute_retrieval_pipeline_with_trace


@pytest.fixture(autouse=True)
def _disable_fixture_shortcuts(monkeypatch) -> None:
    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "0")


def test_build_retrieval_plan_splits_primary_and_mixed_industry_sources() -> None:
    industry_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_hit",
            scores={"policy": 0, "industry": 4, "academic": 0},
        ),
        query="AMD 2025 Form 10-K inventory valuation foundry supply risk factors",
    )

    assert [step.source.source_id for step in industry_plan.first_wave_sources] == [
        "industry_official_or_filings",
        "industry_web_discovery",
        "industry_news_rss",
    ]
    assert industry_plan.global_concurrency_cap == 3

    general_industry_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_hit",
            scores={"policy": 0, "industry": 4, "academic": 0},
        ),
        query="advanced packaging capacity outlook 2026",
    )

    assert [step.source.source_id for step in general_industry_plan.first_wave_sources] == [
        "industry_web_discovery",
    ]
    assert (
        general_industry_plan.fallback_sources[0].fallback_from_source_id
        == "industry_web_discovery"
    )
    assert general_industry_plan.fallback_sources[0].source.source_id == "industry_news_rss"
    assert any(
        step.fallback_from_source_id == "industry_news_rss"
        and step.source.source_id == "industry_official_or_filings"
        for step in general_industry_plan.fallback_sources
    )
    assert general_industry_plan.global_concurrency_cap == 3

    mixed_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_hit",
            scores={"policy": 3, "industry": 2, "academic": 0},
        ),
        query="EU CRA vulnerability handling impact on router vendor support costs",
    )

    assert [step.source.source_id for step in mixed_plan.first_wave_sources] == [
        "policy_official_registry",
        "industry_web_discovery",
        "industry_news_rss",
        "industry_official_or_filings",
    ]
    assert all(
        step.source.is_supplemental
        for step in mixed_plan.first_wave_sources[1:]
    )


def test_default_adapter_registry_exposes_split_industry_sources_and_legacy_alias(
    monkeypatch,
) -> None:
    import skill.api.entry as api_entry

    monkeypatch.delenv("WASC_RETRIEVAL_MODE", raising=False)

    registry = api_entry._default_adapter_registry()

    assert registry["industry_official_or_filings"].__name__ == "search_live"
    assert registry["industry_web_discovery"].__name__ == "search_live"
    assert registry["industry_news_rss"].__name__ == "search_live"
    assert registry["industry_ddgs"].__name__ == "search_live"


def test_execute_retrieval_pipeline_trace_exposes_industry_backup_targets() -> None:
    async def _official_adapter(_: str):
        return []

    async def _web_adapter(_: str):
        return []

    async def _rss_adapter(_: str):
        return []

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_hit",
            scores={"policy": 0, "industry": 4, "academic": 0},
        ),
        query="IATA 2025 cargo demand forecast CTK growth official",
    )

    execution = asyncio.run(
        execute_retrieval_pipeline_with_trace(
            plan=plan,
            query="IATA 2025 cargo demand forecast CTK growth official",
            adapter_registry={
                "industry_official_or_filings": _official_adapter,
                "industry_web_discovery": _web_adapter,
                "industry_news_rss": _rss_adapter,
            },
        )
    )

    trace_by_source = {
        item["source_id"]: item
        for item in execution.retrieval_trace
    }
    assert trace_by_source["industry_web_discovery"]["planner_backup_source_id"] == "industry_news_rss"
    assert trace_by_source["industry_news_rss"]["planner_backup_source_id"] == "industry_official_or_filings"


def test_industry_news_rss_requires_article_body_before_returning_evidence(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="google_news_rss",
                title="IATA cargo demand outlook 2025",
                url="https://news.google.com/rss/articles/abc123",
                snippet="IATA. Tue, 15 Apr 2025 12:00:00 GMT",
                source_url="https://www.iata.org",
            )
        ]

    async def _empty_page_text(**_: object) -> str:
        return ""

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _empty_page_text)

    hits = asyncio.run(
        adapter.search_news_rss_live("IATA 2025 cargo demand forecast CTK growth official")
    )

    assert hits == []


def test_industry_news_rss_fetches_article_body_and_emits_grounded_hit(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="google_news_rss",
                title="IATA cargo demand outlook 2025",
                url="https://news.google.com/rss/articles/abc123",
                snippet="IATA. Tue, 15 Apr 2025 12:00:00 GMT",
                source_url="https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/",
            )
        ]

    async def _article_page_text(**_: object) -> str:
        return (
            "IATA said 2025 cargo demand, measured in CTKs, is expected to grow by "
            "5.8% year over year based on updated industry forecasts."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _article_page_text)

    hits = asyncio.run(
        adapter.search_news_rss_live("IATA 2025 cargo demand forecast CTK growth official")
    )

    assert len(hits) == 1
    assert "5.8% year over year" in hits[0].snippet


def test_industry_news_rss_fetches_original_source_url_and_emits_original_url(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed_urls: list[str] = []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="google_news_rss",
                title="IATA cargo demand outlook 2025",
                url="https://news.google.com/rss/articles/abc123",
                snippet="IATA. Tue, 15 Apr 2025 12:00:00 GMT",
                source_url="https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/",
            )
        ]

    async def _article_page_text(*, url: str, **_: object) -> str:
        observed_urls.append(url)
        return (
            "IATA said 2025 cargo demand, measured in CTKs, is expected to grow by "
            "5.8% year over year based on updated industry forecasts."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(adapter, "fetch_page_text", _article_page_text)

    hits = asyncio.run(
        adapter.search_news_rss_live("IATA 2025 cargo demand forecast CTK growth official")
    )

    assert observed_urls == [
        "https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/"
    ]
    assert len(hits) == 1
    assert hits[0].url == "https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/"


def test_industry_news_rss_resolves_article_url_when_source_url_is_only_homepage(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.industry_ddgs as adapter

    observed_urls: list[str] = []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="google_news_rss",
                title="IATA cargo demand outlook 2025",
                url="https://news.google.com/rss/articles/abc123",
                snippet="IATA. Tue, 15 Apr 2025 12:00:00 GMT",
                source_url="https://www.iata.org",
            )
        ]

    async def _fake_resolve_google_news_article_url(url: str) -> str | None:
        assert url == "https://news.google.com/rss/articles/abc123"
        return "https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/"

    async def _article_page_text(*, url: str, **_: object) -> str:
        observed_urls.append(url)
        return (
            "IATA said 2025 cargo demand, measured in CTKs, is expected to grow by "
            "5.8% year over year based on updated industry forecasts."
        )

    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)
    monkeypatch.setattr(
        adapter.google_news_client,
        "resolve_google_news_article_url",
        _fake_resolve_google_news_article_url,
    )
    monkeypatch.setattr(adapter, "fetch_page_text", _article_page_text)

    hits = asyncio.run(
        adapter.search_news_rss_live("IATA 2025 cargo demand forecast CTK growth official")
    )

    assert observed_urls == [
        "https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/"
    ]
    assert len(hits) == 1
    assert hits[0].url == "https://www.iata.org/en/pressroom/2025-releases/cargo-demand-outlook/"
