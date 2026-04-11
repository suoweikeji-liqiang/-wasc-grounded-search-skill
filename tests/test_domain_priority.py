"""Phase 2 domain-priority and credibility-tier contract tests."""

from __future__ import annotations

from skill.config.retrieval import (
    DOMAIN_FIRST_WAVE_SOURCES,
    SOURCE_CREDIBILITY_TIERS,
    SUPPLEMENTAL_STRONGEST_SOURCE,
)
from skill.retrieval.models import RetrievalHit, derive_credibility_tier


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
