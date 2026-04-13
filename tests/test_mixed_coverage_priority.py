"""Task 3 regressions for query-aware mixed coverage prioritization."""

from __future__ import annotations

from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import prioritize_hits


def test_prioritize_hits_policy_prefers_year_change_and_effective_date_overlap() -> None:
    hits = [
        RetrievalHit(
            source_id="policy_official_registry",
            title="Climate Order administrative bulletin",
            url="https://www.gov.cn/policy/climate-order-bulletin",
            snippet=(
                "Official bulletin with general administrative context and broader compliance "
                "notes that do not answer the requested amendment timing."
            ),
            credibility_tier="official_government",
            authority="State Council",
            jurisdiction="CN",
            publication_date="2026-04-01",
            version="2026-04 bulletin",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Climate Order amendment overview",
            url="https://www.gov.cn/policy/climate-order-amendment",
            snippet="2025 amendment effective date for the climate order.",
            credibility_tier="official_government",
            authority="State Council",
            jurisdiction="CN",
            publication_date="2026-04-01",
        ),
    ]

    ordered = prioritize_hits(
        domain="policy",
        hits=hits,
        primary_route="policy",
        supplemental_route=None,
        query="2025 climate order amendment effective date",
    )

    assert [hit.title for hit in ordered][:2] == [
        "Climate Order amendment overview",
        "Climate Order administrative bulletin",
    ]


def test_prioritize_hits_industry_prefers_chinese_year_and_trend_overlap() -> None:
    ordered = prioritize_hits(
        domain="industry",
        hits=[
            RetrievalHit(
                source_id="industry_ddgs",
                title="Company official handset launch update",
                url="https://www.example.com/company-launch-update",
                snippet="General company update for new handset products.",
                credibility_tier="company_official",
            ),
            RetrievalHit(
                source_id="industry_ddgs",
                title="\u0032\u0030\u0032\u0036\u5e74\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u51fa\u8d27\u91cf\u8d8b\u52bf\u9884\u6d4b",
                url="https://www.example.com/china-smartphone-shipments-2026",
                snippet="\u673a\u6784\u9884\u6d4b\u0032\u0030\u0032\u0036\u5e74\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u51fa\u8d27\u91cf\u5c06\u7ee7\u7eed\u589e\u957f\u3002",
                credibility_tier="trusted_news",
            ),
        ],
        primary_route="industry",
        supplemental_route=None,
        query="\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf\u8d8b\u52bf",
    )

    assert [hit.title for hit in ordered][:2] == [
        "\u0032\u0030\u0032\u0036\u5e74\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u51fa\u8d27\u91cf\u8d8b\u52bf\u9884\u6d4b",
        "Company official handset launch update",
    ]
