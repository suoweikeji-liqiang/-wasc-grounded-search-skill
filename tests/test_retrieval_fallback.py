"""Phase 2 retrieval fallback contract tests."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from skill.api.schema import RetrieveOutcome
from skill.config.retrieval import DOMAIN_FIRST_WAVE_SOURCES, SOURCE_BACKUP_CHAIN
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import (
    PlannedSourceStep,
    RetrievalSource,
    build_retrieval_plan,
)
from skill.retrieval.engine import run_retrieval
from skill.retrieval.fallback_fsm import (
    map_exception_to_failure_reason,
    next_source_for_failure,
)
from skill.retrieval.models import RetrievalFailureReason, RetrievalHit, RetrievalStatus

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "retrieval_phase2_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _mk_hit(source_id: str) -> RetrievalHit:
    return RetrievalHit(
        source_id=source_id,
        title=f"{source_id} title",
        url=f"https://example.com/{source_id}",
        snippet=f"{source_id} snippet",
    )


def test_policy_fallback_chain_is_deterministic_for_no_hits_timeout_and_rate_limited() -> None:
    policy_chain = SOURCE_BACKUP_CHAIN["policy_official_registry"]
    assert policy_chain["no_hits"] == "policy_official_web_allowlist_fallback"
    assert policy_chain["timeout"] == "policy_official_web_allowlist_fallback"
    assert policy_chain["rate_limited"] == "policy_official_web_allowlist_fallback"
    assert "policy_official_web_allowlist_fallback" not in DOMAIN_FIRST_WAVE_SOURCES["policy"]


def test_policy_official_web_allowlist_fallback_only_appears_in_fallback_sources() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    plan = build_retrieval_plan(classification)

    assert all(
        step.source.source_id != "policy_official_web_allowlist_fallback"
        for step in plan.first_wave_sources
    )
    assert any(
        step.source.source_id == "policy_official_web_allowlist_fallback"
        for step in plan.fallback_sources
    )


def test_fallback_fixture_transition_matrix_contract() -> None:
    transitions = [
        case
        for case in _load_cases()
        if case["name"] in {"timeout", "rate_limited_429", "no_hits", "adapter_error"}
    ]
    mapping = {
        case["name"]: SOURCE_BACKUP_CHAIN[case["source_id"]].get(case["failure_reason"])
        for case in transitions
    }

    assert mapping["timeout"] == "policy_official_web_allowlist_fallback"
    assert mapping["rate_limited_429"] == "policy_official_web_allowlist_fallback"
    assert mapping["no_hits"] == "policy_official_web_allowlist_fallback"
    assert mapping["adapter_error"] is None


def test_retrieval_failure_taxonomy_contract() -> None:
    failure_reasons: set[RetrievalFailureReason] = {
        "no_hits",
        "timeout",
        "rate_limited",
        "adapter_error",
    }
    statuses: set[RetrievalStatus] = {"success", "partial", "failure_gaps"}
    assert failure_reasons == {
        "no_hits",
        "timeout",
        "rate_limited",
        "adapter_error",
    }
    assert statuses == {"success", "partial", "failure_gaps"}


def test_retrieve_outcome_failure_gaps_schema_is_strict() -> None:
    outcome = RetrieveOutcome(
        status="failure_gaps",
        failure_reason="adapter_error",
        gaps=["policy_official_registry"],
        results=[],
    )
    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "adapter_error"
    assert outcome.gaps == ["policy_official_registry"]

    with pytest.raises(ValidationError):
        RetrieveOutcome(
            status="unknown_status",
            failure_reason="adapter_error",
            gaps=[],
            results=[],
        )


def test_map_exception_to_failure_reason_maps_timeout_rate_limited_and_adapter_error() -> None:
    class _RateLimitError(RuntimeError):
        status_code = 429

    assert map_exception_to_failure_reason(asyncio.TimeoutError()) == "timeout"
    assert map_exception_to_failure_reason(_RateLimitError("429")) == "rate_limited"
    assert map_exception_to_failure_reason(RuntimeError("boom")) == "adapter_error"


def test_map_exception_to_failure_reason_maps_response_status_code_429_to_rate_limited() -> None:
    class _Response:
        status_code = 429

    class _ResponseRateLimitError(RuntimeError):
        response = _Response()

    assert (
        map_exception_to_failure_reason(_ResponseRateLimitError("response 429"))
        == "rate_limited"
    )


def test_next_source_for_failure_is_deterministic_for_policy_source() -> None:
    assert (
        next_source_for_failure("policy_official_registry", "no_hits")
        == "policy_official_web_allowlist_fallback"
    )
    assert (
        next_source_for_failure("policy_official_registry", "timeout")
        == "policy_official_web_allowlist_fallback"
    )
    assert (
        next_source_for_failure("policy_official_registry", "rate_limited")
        == "policy_official_web_allowlist_fallback"
    )
    assert next_source_for_failure("policy_official_registry", "adapter_error") is None


def test_run_retrieval_invokes_fallback_only_after_first_wave_failure_classification() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    plan = build_retrieval_plan(classification)
    events: list[str] = []

    async def _first_wave(_: str) -> list[RetrievalHit]:
        events.append("first:start")
        await asyncio.sleep(0.01)
        events.append("first:end:no_hits")
        return []

    async def _fallback(_: str) -> list[RetrievalHit]:
        events.append("fallback:start")
        await asyncio.sleep(0.01)
        events.append("fallback:end:success")
        return [_mk_hit("policy_official_web_allowlist_fallback")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="policy source fallback",
            adapter_registry={
                "policy_official_registry": _first_wave,
                "policy_official_web_allowlist_fallback": _fallback,
            },
        )
    )

    assert events == [
        "first:start",
        "first:end:no_hits",
        "fallback:start",
        "fallback:end:success",
    ]
    assert outcome.status == "success"
    assert any(
        hit.source_id == "policy_official_web_allowlist_fallback"
        for hit in outcome.results
    )


def test_run_retrieval_returns_failure_gaps_when_fallback_chain_exhausted() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    plan = build_retrieval_plan(classification)

    async def _first_wave(_: str) -> list[RetrievalHit]:
        return []

    async def _fallback_raises(_: str) -> list[RetrievalHit]:
        raise RuntimeError("fallback adapter_error")

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="policy source fallback exhausted",
            adapter_registry={
                "policy_official_registry": _first_wave,
                "policy_official_web_allowlist_fallback": _fallback_raises,
            },
        )
    )

    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "adapter_error"
    assert set(outcome.gaps) == {
        "policy_official_registry",
        "policy_official_web_allowlist_fallback",
    }
    assert not outcome.results


def test_run_retrieval_response_shaped_429_triggers_fallback_execution() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    plan = build_retrieval_plan(classification)
    events: list[str] = []

    class _Response:
        status_code = 429

    class _ResponseRateLimitError(RuntimeError):
        response = _Response()

    async def _first_wave(_: str) -> list[RetrievalHit]:
        events.append("first:start")
        await asyncio.sleep(0.01)
        events.append("first:end:response_429")
        raise _ResponseRateLimitError("response 429")

    async def _fallback(_: str) -> list[RetrievalHit]:
        events.append("fallback:start")
        await asyncio.sleep(0.01)
        events.append("fallback:end:success")
        return [_mk_hit("policy_official_web_allowlist_fallback")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="policy source response 429 fallback",
            adapter_registry={
                "policy_official_registry": _first_wave,
                "policy_official_web_allowlist_fallback": _fallback,
            },
        )
    )

    assert events == [
        "first:start",
        "first:end:response_429",
        "fallback:start",
        "fallback:end:success",
    ]
    assert outcome.status == "success"
    assert outcome.failure_reason is None
    assert any(
        hit.source_id == "policy_official_web_allowlist_fallback"
        for hit in outcome.results
    )


def test_run_retrieval_primary_academic_parallel_first_wave_returns_arxiv_hit() -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:no_hits")
        return []

    async def _arxiv(_: str) -> list[RetrievalHit]:
        events.append("arxiv:start")
        await asyncio.sleep(0.01)
        events.append("arxiv:end:success")
        return [_mk_hit("academic_arxiv")]

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.01)
        events.append("asta:end:no_hits")
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="single-cell foundation model transcriptomics",
            adapter_registry={
                "academic_semantic_scholar": _semantic_scholar,
                "academic_arxiv": _arxiv,
                "academic_asta_mcp": _asta,
            },
        )
    )

    assert "semantic_scholar:start" in events
    assert "arxiv:start" in events
    assert "asta:start" not in events
    assert outcome.status == "partial"
    assert any(hit.source_id == "academic_arxiv" for hit in outcome.results)


def test_run_retrieval_primary_academic_parallel_first_wave_merges_semantic_and_arxiv_hits() -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=3,
    )
    query = (
        "2025 2026 Europe PMC single-cell foundation model transcriptomics "
        "transformer pretraining cell type annotation"
    )
    events: list[str] = []

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:weak_success")
        return [
            RetrievalHit(
                source_id="academic_semantic_scholar",
                title="Deep Learning in Single-Cell Analysis",
                url="https://example.com/weak-semantic-scholar",
                snippet=(
                    "Survey of single-cell analysis tasks including multimodal integration "
                    "and cell type annotation."
                ),
                year=2022,
                evidence_level="preprint",
            )
        ]

    async def _arxiv(_: str) -> list[RetrievalHit]:
        events.append("arxiv:start")
        await asyncio.sleep(0.01)
        events.append("arxiv:end:success")
        return [
            RetrievalHit(
                source_id="academic_arxiv",
                title=(
                    "Single-cell foundation model pretraining for transcriptomics "
                    "cell type annotation"
                ),
                url="https://example.com/strong-arxiv",
                snippet=(
                    "Transformer pretraining for transcriptomics and cell type "
                    "annotation in single-cell foundation models."
                ),
                year=2026,
                evidence_level="peer_reviewed",
            )
        ]

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.01)
        events.append("asta:end:no_hits")
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query=query,
            adapter_registry={
                "academic_semantic_scholar": _semantic_scholar,
                "academic_arxiv": _arxiv,
                "academic_asta_mcp": _asta,
            },
        )
    )

    assert "semantic_scholar:start" in events
    assert "arxiv:start" in events
    assert "asta:start" not in events
    assert outcome.status == "partial"
    assert {hit.source_id for hit in outcome.results} == {
        "academic_semantic_scholar",
        "academic_arxiv",
    }


def test_run_retrieval_primary_academic_falls_back_to_asta_only_after_metadata_sources_fail() -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:no_hits")
        return []

    async def _arxiv(_: str) -> list[RetrievalHit]:
        events.append("arxiv:start")
        await asyncio.sleep(0.01)
        events.append("arxiv:end:no_hits")
        return []

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.01)
        events.append("asta:end:success")
        return [_mk_hit("academic_asta_mcp")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="single-cell foundation model transcriptomics",
            adapter_registry={
                "academic_semantic_scholar": _semantic_scholar,
                "academic_arxiv": _arxiv,
                "academic_asta_mcp": _asta,
            },
        )
    )

    assert "semantic_scholar:start" in events
    assert "arxiv:start" in events
    assert "asta:start" in events
    assert outcome.status == "partial"
    assert any(hit.source_id == "academic_asta_mcp" for hit in outcome.results)


def test_run_retrieval_primary_academic_caps_asta_fallback_timeout(
    monkeypatch,
) -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.3,
        overall_deadline_seconds=0.6,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:no_hits")
        return []

    async def _arxiv(_: str) -> list[RetrievalHit]:
        events.append("arxiv:start")
        await asyncio.sleep(0.01)
        events.append("arxiv:end:no_hits")
        return []

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.3)
        events.append("asta:end:late-success")
        return [_mk_hit("academic_asta_mcp")]

    import skill.retrieval.engine as engine

    monkeypatch.setattr(engine, "_ACADEMIC_ASTA_FALLBACK_TIMEOUT_SECONDS", 0.05)

    outcome = asyncio.run(
        asyncio.wait_for(
            run_retrieval(
                plan=plan,
                query="multi-source evidence ranking benchmark paper",
                adapter_registry={
                    "academic_semantic_scholar": _semantic_scholar,
                    "academic_arxiv": _arxiv,
                    "academic_asta_mcp": _asta,
                },
            ),
            timeout=0.2,
        )
    )

    assert "asta:start" in events
    assert "asta:end:late-success" not in events
    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "timeout"
    assert not outcome.results


def test_run_retrieval_primary_academic_skips_asta_after_metadata_timeouts() -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:timeout")
        raise asyncio.TimeoutError

    async def _arxiv(_: str) -> list[RetrievalHit]:
        events.append("arxiv:start")
        await asyncio.sleep(0.01)
        events.append("arxiv:end:timeout")
        raise asyncio.TimeoutError

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.01)
        events.append("asta:end:success")
        return [_mk_hit("academic_asta_mcp")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="multi-source evidence ranking benchmark paper",
            adapter_registry={
                "academic_semantic_scholar": _semantic_scholar,
                "academic_arxiv": _arxiv,
                "academic_asta_mcp": _asta,
            },
        )
    )

    assert "semantic_scholar:start" in events
    assert "arxiv:start" in events
    assert "asta:start" not in events
    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "timeout"
    assert not outcome.results


def test_run_retrieval_primary_industry_stops_first_wave_early_after_web_discovery_hit() -> None:
    classification = ClassificationResult(
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        reason_code="industry_hit",
        scores={"policy": 0, "academic": 0, "industry": 5},
    )
    plan = replace(
        build_retrieval_plan(classification, query="advanced packaging capacity outlook 2026"),
        query_variant_budget=1,
        per_source_timeout_seconds=1.0,
        overall_deadline_seconds=0.8,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _web(_: str) -> list[RetrievalHit]:
        events.append("web:start")
        await asyncio.sleep(0.01)
        events.append("web:end:success")
        return [_mk_hit("industry_web_discovery")]

    async def _news(_: str) -> list[RetrievalHit]:
        events.append("news:start")
        try:
            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            events.append("news:cancelled")
            raise
        events.append("news:end:unexpected")
        return []

    async def _official(_: str) -> list[RetrievalHit]:
        events.append("official:start")
        try:
            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            events.append("official:cancelled")
            raise
        events.append("official:end:unexpected")
        return []

    started_at = time.perf_counter()
    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="advanced packaging capacity outlook 2026",
            adapter_registry={
                "industry_web_discovery": _web,
                "industry_news_rss": _news,
                "industry_official_or_filings": _official,
            },
        )
    )
    elapsed = time.perf_counter() - started_at

    assert outcome.status == "success"
    assert any(hit.source_id == "industry_web_discovery" for hit in outcome.results)
    assert "news:start" not in events
    assert "official:start" not in events
    assert elapsed < 0.2


def test_run_retrieval_primary_industry_packaging_query_stops_after_first_no_hit_variant() -> None:
    classification = ClassificationResult(
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        reason_code="industry_hit",
        scores={"policy": 0, "academic": 0, "industry": 5},
    )
    plan = replace(
        build_retrieval_plan(classification, query="advanced packaging capacity outlook 2026"),
        query_variant_budget=5,
        per_source_timeout_seconds=1.0,
        overall_deadline_seconds=0.5,
        global_concurrency_cap=3,
    )
    observed_queries: dict[str, list[str]] = {
        "industry_web_discovery": [],
        "industry_news_rss": [],
        "industry_official_or_filings": [],
    }

    async def _web(query: str) -> list[RetrievalHit]:
        observed_queries["industry_web_discovery"].append(query)
        return []

    async def _news(query: str) -> list[RetrievalHit]:
        observed_queries["industry_news_rss"].append(query)
        return []

    async def _official(query: str) -> list[RetrievalHit]:
        observed_queries["industry_official_or_filings"].append(query)
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="advanced packaging capacity outlook 2026",
            adapter_registry={
                "industry_web_discovery": _web,
                "industry_news_rss": _news,
                "industry_official_or_filings": _official,
            },
        )
    )

    assert outcome.status == "failure_gaps"
    assert observed_queries == {
        "industry_web_discovery": ["advanced packaging capacity outlook 2026"],
        "industry_news_rss": ["advanced packaging capacity outlook 2026"],
        "industry_official_or_filings": ["advanced packaging capacity outlook 2026"],
    }


def test_run_retrieval_primary_industry_packaging_query_uses_fallback_chain_after_web_discovery_failure() -> None:
    classification = ClassificationResult(
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        reason_code="industry_hit",
        scores={"policy": 0, "academic": 0, "industry": 5},
    )
    plan = replace(
        build_retrieval_plan(classification, query="advanced packaging capacity outlook 2026"),
        query_variant_budget=1,
        per_source_timeout_seconds=0.2,
        overall_deadline_seconds=0.5,
        global_concurrency_cap=3,
    )
    observed_calls: list[str] = []

    async def _web(_: str) -> list[RetrievalHit]:
        observed_calls.append("industry_web_discovery")
        return []

    async def _news(_: str) -> list[RetrievalHit]:
        observed_calls.append("industry_news_rss")
        return []

    async def _official(_: str) -> list[RetrievalHit]:
        observed_calls.append("industry_official_or_filings")
        return []

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="advanced packaging capacity outlook 2026",
            adapter_registry={
                "industry_web_discovery": _web,
                "industry_news_rss": _news,
                "industry_official_or_filings": _official,
            },
        )
    )

    assert outcome.status == "failure_gaps"
    assert observed_calls == [
        "industry_web_discovery",
        "industry_news_rss",
        "industry_official_or_filings",
    ]


def test_run_retrieval_mixed_supplemental_academic_skips_asta_fallback_after_primary_success() -> None:
    classification = ClassificationResult(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="academic",
        reason_code="explicit_cross_domain",
        scores={"policy": 5, "academic": 4, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        query_variant_budget=1,
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.2,
        global_concurrency_cap=3,
    )
    events: list[str] = []

    async def _policy(_: str) -> list[RetrievalHit]:
        events.append("policy:start")
        await asyncio.sleep(0.01)
        events.append("policy:end:success")
        return [_mk_hit("policy_official_registry")]

    async def _semantic_scholar(_: str) -> list[RetrievalHit]:
        events.append("semantic_scholar:start")
        await asyncio.sleep(0.01)
        events.append("semantic_scholar:end:timeout")
        raise asyncio.TimeoutError

    async def _asta(_: str) -> list[RetrievalHit]:
        events.append("asta:start")
        await asyncio.sleep(0.01)
        events.append("asta:end:success")
        return [_mk_hit("academic_asta_mcp")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="AI chip export controls effect on academic research",
            adapter_registry={
                "policy_official_registry": _policy,
                "academic_semantic_scholar": _semantic_scholar,
                "academic_asta_mcp": _asta,
            },
        )
    )

    assert "policy:start" in events
    assert "semantic_scholar:start" in events
    assert "asta:start" not in events
    assert outcome.status == "partial"
    assert any(hit.source_id == "policy_official_registry" for hit in outcome.results)


def test_run_retrieval_empty_fallback_sources_skips_fallback_execution() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    base_plan = build_retrieval_plan(classification)
    plan = replace(base_plan, fallback_sources=())
    events: list[str] = []

    async def _first_wave(_: str) -> list[RetrievalHit]:
        events.append("first:start")
        await asyncio.sleep(0.01)
        events.append("first:end:no_hits")
        return []

    async def _fallback(_: str) -> list[RetrievalHit]:
        events.append("fallback:unexpected")
        return [_mk_hit("policy_official_web_allowlist_fallback")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="policy source empty fallback",
            adapter_registry={
                "policy_official_registry": _first_wave,
                "policy_official_web_allowlist_fallback": _fallback,
            },
        )
    )

    assert events == [
        "first:start",
        "first:end:no_hits",
    ]
    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "no_hits"
    assert outcome.gaps == ("policy_official_registry",)
    assert not outcome.results


def test_run_retrieval_fallback_sources_map_controls_transition_selection() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 5, "academic": 0, "industry": 0},
    )
    base_plan = build_retrieval_plan(classification)
    custom_fallback = PlannedSourceStep(
        source=RetrievalSource(
            source_id="academic_semantic_scholar",
            route="policy",
        ),
        fallback_from_source_id="policy_official_registry",
        trigger_on_failures=("no_hits",),
    )
    plan = replace(base_plan, fallback_sources=(custom_fallback,))
    events: list[str] = []

    async def _first_wave(_: str) -> list[RetrievalHit]:
        events.append("first:start")
        await asyncio.sleep(0.01)
        events.append("first:end:no_hits")
        return []

    async def _custom_fallback(_: str) -> list[RetrievalHit]:
        events.append("fallback:custom")
        await asyncio.sleep(0.01)
        return [_mk_hit("academic_semantic_scholar")]

    async def _global_chain_fallback(_: str) -> list[RetrievalHit]:
        events.append("fallback:global_unexpected")
        return [_mk_hit("policy_official_web_allowlist_fallback")]

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="policy source custom fallback map",
            adapter_registry={
                "policy_official_registry": _first_wave,
                "academic_semantic_scholar": _custom_fallback,
                "policy_official_web_allowlist_fallback": _global_chain_fallback,
            },
        )
    )

    assert events == [
        "first:start",
        "first:end:no_hits",
        "fallback:custom",
    ]
    assert outcome.status == "success"
    assert outcome.failure_reason is None
    assert any(hit.source_id == "academic_semantic_scholar" for hit in outcome.results)
