from __future__ import annotations

import asyncio

from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import run_retrieval
from skill.retrieval.models import RetrievalHit
from skill.retrieval.query_variants import build_query_variants


def test_build_query_variants_caps_policy_expansion_and_dedupes() -> None:
    variants = build_query_variants(
        query="\u0032\u0030\u0032\u0035\u5e74\u6570\u636e\u51fa\u5883\u5b89\u5168\u8bc4\u4f30\u529e\u6cd5\u6709\u54ea\u4e9b\u53d8\u5316",
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        target_route="policy",
    )

    assert 1 <= len(variants) <= 3
    assert variants[0].reason_code == "original"
    assert len({item.query for item in variants}) == len(variants)
    assert any("\u53d8\u5316" in item.query or "\u4fee\u8ba2" in item.query for item in variants)


def test_build_query_variants_builds_route_specific_mixed_variants() -> None:
    policy_variants = build_query_variants(
        query="AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd",
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        target_route="policy",
    )
    industry_variants = build_query_variants(
        query="AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd",
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        target_route="industry",
    )

    assert len(policy_variants) <= 3
    assert len(industry_variants) <= 3
    assert any("act" in item.query.lower() for item in policy_variants)
    assert any(
        "\u4ea7\u4e1a" in item.query or "\u5e02\u573a" in item.query or "\u9884\u6d4b" in item.query
        for item in industry_variants
    )


def test_run_retrieval_uses_query_variants_and_merges_hits() -> None:
    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    observed_queries: list[str] = []

    async def _industry_adapter(query: str) -> list[RetrievalHit]:
        observed_queries.append(query)
        if "\u9884\u6d4b" not in query and "\u8d8b\u52bf" not in query:
            return []
        return [
            RetrievalHit(
                source_id="industry_ddgs",
                title="variant-hit",
                url="https://example.com/variant-hit",
                snippet=f"Hit from {query}",
                credibility_tier="trusted_news",
            )
        ]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf",
            adapter_registry={"industry_ddgs": _industry_adapter},
        )
    )

    assert outcome.status == "success"
    assert len(observed_queries) >= 2
    assert len(outcome.results) == 1
    assert outcome.results[0].title == "variant-hit"


def test_run_retrieval_merges_unique_hits_across_successful_variants() -> None:
    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    observed_queries: list[str] = []
    original_query = "\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf"

    async def _industry_adapter(query: str) -> list[RetrievalHit]:
        observed_queries.append(query)
        hits: list[RetrievalHit] = []
        if query == original_query:
            hits.append(
                RetrievalHit(
                    source_id="industry_ddgs",
                    title="original-hit",
                    url="https://example.com/original-hit",
                    snippet="Hit from original query",
                    credibility_tier="trusted_news",
                )
            )
        if "\u9884\u6d4b" in query or "\u8d8b\u52bf" in query:
            hits.append(
                RetrievalHit(
                    source_id="industry_ddgs",
                    title="variant-hit",
                    url="https://example.com/variant-hit",
                    snippet=f"Hit from {query}",
                    credibility_tier="trusted_news",
                )
            )
        return hits

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=original_query,
            adapter_registry={"industry_ddgs": _industry_adapter},
        )
    )

    assert outcome.status == "success"
    assert len(observed_queries) >= 2
    assert len(outcome.results) == 2
    assert {item.title for item in outcome.results} == {"original-hit", "variant-hit"}
