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


def test_prioritize_hits_industry_prefers_cjk_gloss_semantic_match_over_generic_impact_overlap() -> None:
    ordered = prioritize_hits(
        domain="industry",
        hits=[
            RetrievalHit(
                source_id="industry_ddgs",
                title="AI Act 对开源模型产业落地影响评估",
                url="https://www.bloomberg.com/news/articles/2026-04-08/ai-act-open-source-model-deployment-impact",
                snippet="行业分析认为 AI Act 将改变开源模型商业化、企业部署和产业落地节奏。",
                credibility_tier="trusted_news",
            ),
            RetrievalHit(
                source_id="industry_ddgs",
                title="BYD autonomous driving supplier investment update",
                url="https://www.byd.com/news/autonomous-driving-supplier-investment-2026",
                snippet="Company update says autonomous driving programs are increasing supplier investment across the vehicle industry in 2026.",
                credibility_tier="company_official",
            ),
            RetrievalHit(
                source_id="industry_ddgs",
                title="Vision Pro XR 市场销量展望",
                url="https://www.counterpointresearch.com/insights/vision-pro-sales-outlook-2026",
                snippet="机构预测 Vision Pro 销量与后续出货节奏将影响高端 XR 市场走势。",
                credibility_tier="trusted_news",
            ),
        ],
        primary_route="policy",
        supplemental_route="industry",
        query="自动驾驶试点监管变化对产业投资影响",
    )

    assert ordered[0].title == "BYD autonomous driving supplier investment update"
