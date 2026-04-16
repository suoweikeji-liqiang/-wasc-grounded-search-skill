from __future__ import annotations

import asyncio
from dataclasses import replace

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


def test_build_query_variants_condenses_long_academic_queries() -> None:
    query = (
        "2025 paper mixture-of-experts routing stability load balancing "
        "auxiliary loss collapse mitigation"
    )

    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
    )

    assert variants[0].reason_code == "original"
    assert any(
        item.reason_code == "academic_topic_focus"
        and "2025" not in item.query
        and "paper" not in item.query.lower()
        and "mixture-of-experts" in item.query
        and "load balancing" in item.query
        for item in variants
    )
    assert len(variants) <= 3


def test_build_query_variants_adds_condensed_repository_hints_for_academic_queries() -> None:
    query = (
        "2025 2026 Europe PMC single-cell foundation model transcriptomics "
        "transformer pretraining cell type annotation"
    )

    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
    )

    assert any(
        item.reason_code == "academic_source_hint"
        and "europe pmc" in item.query.lower()
        and "2025" not in item.query
        and "single-cell" in item.query
        and "cell type annotation" in item.query
        for item in variants
    )


def test_build_query_variants_adds_ascii_core_for_cjk_academic_queries() -> None:
    variants = build_query_variants(
        query="有哪些 grounded search evidence packing 论文",
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "academic_ascii_core"
        and item.query == "grounded search evidence packing"
        for item in variants
    )


def test_build_query_variants_adds_ascii_core_for_placeholder_noisy_academic_queries() -> None:
    variants = build_query_variants(
        query="??? grounded search evidence packing ??",
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "academic_ascii_core"
        and item.query == "grounded search evidence packing"
        for item in variants
    )


def test_build_query_variants_adds_phrase_locked_academic_variant_for_strong_technical_phrases() -> None:
    query = (
        "2025 2026 arXiv test-time scaling large language models "
        "compute-optimal inference best-of-n reranking"
    )

    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "academic_phrase_locked"
        and '"' in item.query
        and "test-time scaling" in item.query
        and "best-of-n reranking" in item.query
        and "2025" not in item.query
        for item in variants
    )


def test_build_query_variants_adds_evidence_type_focus_for_academic_queries() -> None:
    query = (
        "2025 retrieval-augmented generation citation grounding "
        "evaluation dataset factuality attribution"
    )

    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "academic_evidence_type_focus"
        and "2025" not in item.query
        and "dataset" in item.query
        and "evaluation" in item.query
        and "citation" in item.query
        for item in variants
    )


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


def test_build_query_variants_adds_structural_cross_domain_fragments_for_mixed_queries() -> None:
    query = "EU DORA ICT incident reporting timeline and SaaS vendor incident update notice"

    policy_variants = build_query_variants(
        query=query,
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        target_route="policy",
        variant_limit=5,
    )
    industry_variants = build_query_variants(
        query=query,
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        target_route="industry",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "cross_domain_fragment_focus"
        and "dora" in item.query.lower()
        and "saas vendor" not in item.query.lower()
        for item in policy_variants
    )
    assert any(
        item.reason_code == "cross_domain_fragment_focus"
        and "saas vendor" in item.query.lower()
        and "dora" not in item.query.lower()
        for item in industry_variants
    )


def test_build_query_variants_adds_structural_document_focus_for_filing_queries() -> None:
    query = "Visa 2025 Form 10-K payments volume processed transactions definitions"

    variants = build_query_variants(
        query=query,
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        target_route="industry",
        variant_limit=5,
    )

    assert any(
        item.reason_code == "document_focus"
        and "visa" in item.query.lower()
        and "form 10-k" in item.query.lower()
        and "payments volume" in item.query.lower()
        and "processed transactions" in item.query.lower()
        for item in variants
    )
    assert any(
        item.reason_code == "document_concept_focus"
        and "visa" in item.query.lower()
        and "payments volume" in item.query.lower()
        and "processed transactions" in item.query.lower()
        and "definition" not in item.query.lower()
        for item in variants
    )


def test_run_retrieval_uses_query_variants_and_merges_hits() -> None:
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    web_step = next(
        step
        for step in base_plan.first_wave_sources
        if step.source.source_id == "industry_web_discovery"
    )
    plan = replace(
        base_plan,
        first_wave_sources=(web_step,),
        fallback_sources=(),
        global_concurrency_cap=1,
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
            adapter_registry={web_step.source.source_id: _industry_adapter},
        )
    )

    assert outcome.status == "success"
    assert len(observed_queries) >= 2
    assert len(outcome.results) == 1
    assert outcome.results[0].title == "variant-hit"


def test_run_retrieval_merges_unique_hits_across_successful_variants() -> None:
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    web_step = next(
        step
        for step in base_plan.first_wave_sources
        if step.source.source_id == "industry_web_discovery"
    )
    plan = replace(
        base_plan,
        first_wave_sources=(web_step,),
        fallback_sources=(),
        global_concurrency_cap=1,
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
            adapter_registry={web_step.source.source_id: _industry_adapter},
        )
    )

    assert outcome.status == "success"
    assert len(observed_queries) >= 2
    assert len(outcome.results) == 2
    assert {item.title for item in outcome.results} == {"original-hit", "variant-hit"}


def test_run_retrieval_merges_variant_provenance_for_duplicate_hits() -> None:
    query = "Visa 2025 Form 10-K payments volume processed transactions definitions"
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        query_variant_budget=5,
        global_concurrency_cap=1,
    )
    variants = build_query_variants(
        query=query,
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        target_route="industry",
        variant_limit=5,
    )
    document_focus_query = next(
        item.query for item in variants if item.reason_code == "document_focus"
    )
    observed_queries: list[str] = []

    async def _industry_adapter(candidate_query: str) -> list[RetrievalHit]:
        observed_queries.append(candidate_query)
        if candidate_query not in {query, document_focus_query}:
            return []
        return [
            RetrievalHit(
                source_id=first_step.source.source_id,
                title="visa-form-10k-definitions",
                url="https://example.com/visa-form-10k-definitions",
                snippet=(
                    "Visa Form 10-K defines payments volume and processed transactions."
                ),
                credibility_tier="company_official",
            )
        ]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={first_step.source.source_id: _industry_adapter},
        )
    )

    assert outcome.status == "success"
    assert observed_queries[:2] == [query, document_focus_query]
    assert len(outcome.results) == 1
    assert outcome.results[0].target_route == "industry"
    assert set(outcome.results[0].variant_reason_codes) == {
        "original",
        "document_focus",
    }
    assert set(outcome.results[0].variant_queries) == {
        query,
        document_focus_query,
    }


def test_run_retrieval_prioritizes_condensed_academic_variants_when_timeout_limited() -> None:
    query = (
        "2025 paper mixture-of-experts routing stability load balancing "
        "auxiliary loss collapse mitigation"
    )
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="academic",
            primary_route="academic",
            supplemental_route=None,
            reason_code="academic_keywords",
            scores={"policy": 0, "academic": 5, "industry": 0},
        )
    )
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.12,
        overall_deadline_seconds=0.3,
        global_concurrency_cap=1,
    )
    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
    )
    topic_focus_query = next(
        item.query for item in variants if item.reason_code == "academic_topic_focus"
    )
    observed_queries: list[str] = []

    async def _academic_adapter(candidate_query: str) -> list[RetrievalHit]:
        observed_queries.append(candidate_query)
        if candidate_query == topic_focus_query:
            await asyncio.sleep(0.01)
            return [
                RetrievalHit(
                    source_id=first_step.source.source_id,
                    title="moe-load-balancing",
                    url="https://example.com/moe-load-balancing",
                    snippet="Mixture-of-experts routing stability and load balancing paper.",
                )
            ]

        await asyncio.sleep(0.25)
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={first_step.source.source_id: _academic_adapter},
        )
    )

    assert observed_queries[0] == topic_focus_query
    assert outcome.status == "success"
    assert len(outcome.results) == 1
    assert outcome.results[0].title == "moe-load-balancing"


def test_run_retrieval_stops_academic_source_after_first_successful_variant() -> None:
    query = (
        "2025 paper mixture-of-experts routing stability load balancing "
        "auxiliary loss collapse mitigation"
    )
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="academic",
            primary_route="academic",
            supplemental_route=None,
            reason_code="academic_keywords",
            scores={"policy": 0, "academic": 5, "industry": 0},
        )
    )
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.3,
        overall_deadline_seconds=0.4,
        global_concurrency_cap=1,
    )
    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
    )
    topic_focus_query = next(
        item.query for item in variants if item.reason_code == "academic_topic_focus"
    )
    observed_queries: list[str] = []

    async def _academic_adapter(candidate_query: str) -> list[RetrievalHit]:
        observed_queries.append(candidate_query)
        if candidate_query == topic_focus_query:
            await asyncio.sleep(0.01)
            return [
                RetrievalHit(
                    source_id=first_step.source.source_id,
                    title="moe-load-balancing",
                    url="https://example.com/moe-load-balancing",
                    snippet="Mixture-of-experts routing stability and load balancing paper.",
                )
            ]
        await asyncio.sleep(0.01)
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={first_step.source.source_id: _academic_adapter},
        )
    )

    assert observed_queries == [topic_focus_query]
    assert outcome.status == "success"
    assert len(outcome.results) == 1
    assert outcome.results[0].title == "moe-load-balancing"


def test_run_retrieval_prioritizes_source_and_phrase_locked_academic_variants_before_original() -> None:
    query = (
        "2025 2026 arXiv test-time scaling large language models "
        "compute-optimal inference best-of-n reranking"
    )
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="academic",
            primary_route="academic",
            supplemental_route=None,
            reason_code="academic_keywords",
            scores={"policy": 0, "academic": 5, "industry": 0},
        )
    )
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.16,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=1,
    )
    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=4,
    )
    source_hint_query = next(
        (item.query for item in variants if item.reason_code == "academic_source_hint"),
        None,
    )
    phrase_locked_query = next(
        (item.query for item in variants if item.reason_code == "academic_phrase_locked"),
        None,
    )

    assert source_hint_query is not None
    assert phrase_locked_query is not None

    observed_queries: list[str] = []

    async def _academic_adapter(candidate_query: str) -> list[RetrievalHit]:
        observed_queries.append(candidate_query)
        if candidate_query == phrase_locked_query:
            await asyncio.sleep(0.01)
            return [
                RetrievalHit(
                    source_id=first_step.source.source_id,
                    title="test-time-scaling-reranking",
                    url="https://example.com/test-time-scaling-reranking",
                    snippet="Test-time scaling and best-of-n reranking paper.",
                )
            ]

        await asyncio.sleep(0.08)
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={first_step.source.source_id: _academic_adapter},
        )
    )

    assert observed_queries[:2] == [source_hint_query, phrase_locked_query]
    assert outcome.status == "success"
    assert outcome.results[0].title == "test-time-scaling-reranking"


def test_run_retrieval_prioritizes_ascii_core_academic_variant_before_original() -> None:
    query = "有哪些 grounded search evidence packing 论文"
    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="academic",
            primary_route="academic",
            supplemental_route=None,
            reason_code="academic_keywords",
            scores={"policy": 0, "academic": 5, "industry": 0},
        )
    )
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.16,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=1,
    )
    variants = build_query_variants(
        query=query,
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        target_route="academic",
        variant_limit=5,
    )
    ascii_core_query = next(
        (item.query for item in variants if item.reason_code == "academic_ascii_core"),
        None,
    )

    assert ascii_core_query == "grounded search evidence packing"

    observed_queries: list[str] = []

    async def _academic_adapter(candidate_query: str) -> list[RetrievalHit]:
        observed_queries.append(candidate_query)
        if candidate_query == ascii_core_query:
            await asyncio.sleep(0.01)
            return [
                RetrievalHit(
                    source_id=first_step.source.source_id,
                    title="grounded-search-evidence-packing",
                    url="https://example.com/grounded-search-evidence-packing",
                    snippet="Grounded search evidence packing paper.",
                )
            ]
        await asyncio.sleep(0.08)
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={first_step.source.source_id: _academic_adapter},
        )
    )

    assert observed_queries[0] == ascii_core_query
    assert outcome.status == "success"
    assert outcome.results[0].title == "grounded-search-evidence-packing"


def test_build_retrieval_plan_extends_time_budget_for_primary_industry_queries() -> None:
    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    mixed_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )

    assert plan.per_source_timeout_seconds == 8.0
    assert plan.overall_deadline_seconds == 9.0
    assert mixed_plan.per_source_timeout_seconds == 3.0
    assert mixed_plan.overall_deadline_seconds == 8.0


def test_build_retrieval_plan_widens_variant_budget_for_generalization_sensitive_routes() -> None:
    policy_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            reason_code="policy_keywords",
            scores={"policy": 5, "academic": 0, "industry": 0},
        )
    )
    industry_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_keywords",
            scores={"policy": 0, "academic": 0, "industry": 5},
        )
    )
    mixed_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )

    assert policy_plan.query_variant_budget == 3
    assert industry_plan.query_variant_budget == 5
    assert mixed_plan.query_variant_budget == 5


def test_build_retrieval_plan_partitions_mixed_budget_for_discovery_and_deep_fetch() -> None:
    mixed_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )

    assert mixed_plan.overall_deadline_seconds == 8.0
    assert mixed_plan.mixed_discovery_deadline_seconds == 2.5
    assert mixed_plan.mixed_deep_deadline_seconds == 5.0
    assert mixed_plan.mixed_shortlist_top_k == 4
    assert mixed_plan.mixed_pooled_enabled is True
