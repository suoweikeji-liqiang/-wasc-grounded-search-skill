"""Phase 2 domain-priority and credibility-tier contract tests."""

from __future__ import annotations

import asyncio

from skill.config.retrieval import (
    DOMAIN_FIRST_WAVE_SOURCES,
    SOURCE_CREDIBILITY_TIERS,
    SUPPLEMENTAL_STRONGEST_SOURCE,
)
from skill.retrieval.models import RetrievalHit, derive_credibility_tier
from skill.retrieval.priority import prioritize_hits


def test_policy_route_keeps_fallback_outside_first_wave() -> None:
    assert DOMAIN_FIRST_WAVE_SOURCES["policy"] == ("policy_official_registry",)
    assert "policy_official_web_allowlist_fallback" not in DOMAIN_FIRST_WAVE_SOURCES["policy"]


def test_mixed_supplemental_route_uses_strongest_single_source() -> None:
    assert SUPPLEMENTAL_STRONGEST_SOURCE["policy"] == "policy_official_registry"
    assert SUPPLEMENTAL_STRONGEST_SOURCE["academic"] == "academic_semantic_scholar"
    assert SUPPLEMENTAL_STRONGEST_SOURCE["industry"] == "industry_ddgs"


def test_industry_source_has_credibility_tier_mapping() -> None:
    assert "industry_ddgs" in SOURCE_CREDIBILITY_TIERS
    assert SOURCE_CREDIBILITY_TIERS["industry_ddgs"] == "trusted_news"


def test_retrieval_hit_contract_has_credibility_tier_or_derivation() -> None:
    hit = RetrievalHit(
        source_id="industry_ddgs",
        title="Example industry report",
        url="https://example.com/industry",
        snippet="Example snippet",
    )
    assert hit.credibility_tier == "trusted_news"
    assert derive_credibility_tier("industry_ddgs") == SOURCE_CREDIBILITY_TIERS["industry_ddgs"]


def test_retrieval_hit_explicit_credibility_tier_is_preserved() -> None:
    hit = RetrievalHit(
        source_id="industry_ddgs",
        title="Example official source",
        url="https://example.com/official",
        snippet="Example snippet",
        credibility_tier="company_official",
    )
    assert hit.credibility_tier == "company_official"


def test_policy_allowlist_adapter_emits_only_official_policy_domains() -> None:
    from skill.retrieval.adapters.policy_official_web_allowlist import search

    hits = asyncio.run(search("latest emissions regulation"))

    assert hits
    assert all(hit.source_id == "policy_official_web_allowlist_fallback" for hit in hits)
    assert all("blog.example.com" not in hit.url for hit in hits)
    assert any("gov.cn" in hit.url for hit in hits)


def test_academic_adapters_emit_scholarly_source_ids_only() -> None:
    from skill.retrieval.adapters.academic_arxiv import search as search_arxiv
    from skill.retrieval.adapters.academic_semantic_scholar import (
        search as search_semantic_scholar,
    )

    semantic_hits = asyncio.run(search_semantic_scholar("graph neural retrieval"))
    arxiv_hits = asyncio.run(search_arxiv("graph neural retrieval"))
    all_hits = semantic_hits + arxiv_hits

    assert semantic_hits
    assert arxiv_hits
    assert all_hits
    assert all(
        hit.source_id in {"academic_semantic_scholar", "academic_arxiv"}
        for hit in all_hits
    )


def test_industry_tier_adapter_assigns_explicit_credibility_tiers() -> None:
    from skill.retrieval.adapters.industry_ddgs import search

    hits = asyncio.run(search("global battery market forecast"))
    observed_tiers = {hit.credibility_tier for hit in hits}

    assert hits
    assert None not in observed_tiers
    assert observed_tiers.issubset(
        {"company_official", "industry_association", "trusted_news", "general_web"}
    )
    assert "company_official" in observed_tiers


def test_industry_adapter_prefers_exact_query_match_over_generic_higher_tier_fixture() -> None:
    from skill.retrieval.adapters.industry_ddgs import search

    hits = asyncio.run(search("semiconductor packaging capacity forecast 2026"))

    assert hits
    assert hits[0].title == "SEMI outlook for semiconductor packaging capacity"
    assert hits[0].credibility_tier == "industry_association"


def test_prioritize_hits_policy_domain_first_d15_before_generic_relevance() -> None:
    hits = [
        RetrievalHit(
            source_id="policy_official_web_allowlist_fallback",
            title="Highly relevant policy summary",
            url="https://www.gov.cn/zhengce/summary",
            snippet="Secondary interpretation with many keywords.",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Official policy source text",
            url="https://www.mee.gov.cn/policy/original",
            snippet="Primary source publication.",
        ),
    ]

    ordered = prioritize_hits(
        domain="policy",
        hits=hits,
        primary_route="policy",
        supplemental_route=None,
    )

    assert [hit.source_id for hit in ordered] == [
        "policy_official_registry",
        "policy_official_web_allowlist_fallback",
    ]


def test_prioritize_hits_academic_excludes_non_scholarly_candidates() -> None:
    hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Semantic Scholar paper",
            url="https://www.semanticscholar.org/paper/123",
            snippet="Scholarly source.",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="Generic web page",
            url="https://example.com/blog",
            snippet="Non-scholarly source that must be excluded.",
        ),
    ]

    ordered = prioritize_hits(
        domain="academic",
        hits=hits,
        primary_route="academic",
        supplemental_route=None,
    )

    assert [hit.source_id for hit in ordered] == ["academic_semantic_scholar"]


def test_prioritize_hits_industry_tier_then_recency_within_tier() -> None:
    hits = [
        RetrievalHit(
            source_id="industry_ddgs",
            title="Trusted News Older",
            url="https://www.reuters.com/world/2024-01-01/market",
            snippet="Older trusted-news source.",
            credibility_tier="trusted_news",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="Company Official Update",
            url="https://www.tesla.com/blog/2025-06-01-update",
            snippet="Highest credibility tier.",
            credibility_tier="company_official",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="Trusted News Newer",
            url="https://www.reuters.com/world/2026-02-15/market",
            snippet="Newer trusted-news source.",
            credibility_tier="trusted_news",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="General Web Post",
            url="https://example.net/post",
            snippet="Lowest credibility tier.",
            credibility_tier="general_web",
        ),
    ]

    ordered = prioritize_hits(
        domain="industry",
        hits=hits,
        primary_route="industry",
        supplemental_route=None,
    )

    assert [hit.title for hit in ordered] == [
        "Company Official Update",
        "Trusted News Newer",
        "Trusted News Older",
        "General Web Post",
    ]


def test_prioritize_hits_industry_prefers_query_match_when_query_available() -> None:
    hits = [
        RetrievalHit(
            source_id="industry_ddgs",
            title="Company Official Battery Update",
            url="https://www.tesla.com/blog/2025-06-01-update",
            snippet="Generic battery production guidance.",
            credibility_tier="company_official",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="SEMI outlook for semiconductor packaging capacity",
            url="https://www.semi.org/en/news-resources/market-data/packaging-capacity-2026",
            snippet="Industry-association forecast for semiconductor packaging capacity in 2026.",
            credibility_tier="industry_association",
        ),
        RetrievalHit(
            source_id="industry_ddgs",
            title="Trusted News Battery Pricing",
            url="https://www.reuters.com/world/2026-02-15/market",
            snippet="Trusted news on battery pricing.",
            credibility_tier="trusted_news",
        ),
    ]

    ordered = prioritize_hits(
        domain="industry",
        hits=hits,
        primary_route="industry",
        supplemental_route=None,
        query="semiconductor packaging capacity forecast 2026",
    )

    assert [hit.title for hit in ordered][:2] == [
        "SEMI outlook for semiconductor packaging capacity",
        "Company Official Battery Update",
    ]
