"""Phase 2 retrieval runtime tests for first-wave fan-out behavior."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from skill.config.retrieval import (
    DOMAIN_FIRST_WAVE_SOURCES,
    GLOBAL_CONCURRENCY_CAP,
    OVERALL_RETRIEVAL_DEADLINE_SECONDS,
    PER_SOURCE_TIMEOUT_SECONDS,
)
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import run_retrieval
from skill.retrieval.models import RetrievalHit

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "retrieval_phase2_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _source_ids_for(plan: Any, *, route: str, supplemental_only: bool) -> list[str]:
    return [
        step.source.source_id
        for step in plan.first_wave_sources
        if step.source.route == route and step.source.is_supplemental == supplemental_only
    ]


def _mk_hit(source_id: str) -> RetrievalHit:
    return RetrievalHit(
        source_id=source_id,
        title=f"{source_id} title",
        url=f"https://example.com/{source_id}",
        snippet=f"{source_id} snippet",
    )


def test_retrieval_deadline_budget_contract_constants() -> None:
    assert PER_SOURCE_TIMEOUT_SECONDS == 3.0
    assert OVERALL_RETRIEVAL_DEADLINE_SECONDS == 6.0
    assert GLOBAL_CONCURRENCY_CAP == 6


def test_policy_first_wave_excludes_policy_official_web_allowlist_fallback() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 4, "academic": 0, "industry": 0},
    )
    plan = build_retrieval_plan(classification)

    first_wave_ids = [step.source.source_id for step in plan.first_wave_sources]
    fallback_ids = [step.source.source_id for step in plan.fallback_sources]

    assert "policy_official_registry" in first_wave_ids
    assert "policy_official_web_allowlist_fallback" not in first_wave_ids
    assert "policy_official_web_allowlist_fallback" in fallback_ids
    assert "policy_official_web_allowlist_fallback" not in DOMAIN_FIRST_WAVE_SOURCES["policy"]


def test_mixed_route_uses_full_primary_plus_single_supplemental_source() -> None:
    mixed_case = next(
        item
        for item in _load_cases()
        if item["name"] == "mixed_primary_with_single_supplemental_source"
    )
    classification = ClassificationResult(
        route_label=mixed_case["route_label"],
        primary_route=mixed_case["primary_route"],
        supplemental_route=mixed_case["supplemental_route"],
        reason_code="explicit_cross_domain",
        scores={"policy": 0, "academic": 6, "industry": 5},
    )

    plan = build_retrieval_plan(classification)

    primary_first_wave_ids = _source_ids_for(
        plan, route=mixed_case["primary_route"], supplemental_only=False
    )
    supplemental_first_wave_ids = _source_ids_for(
        plan, route=mixed_case["supplemental_route"], supplemental_only=True
    )

    assert primary_first_wave_ids == mixed_case["expected_primary_first_wave"]
    assert supplemental_first_wave_ids == mixed_case["expected_supplemental_first_wave"]


def test_run_retrieval_first_wave_only_excludes_policy_official_web_allowlist_fallback() -> None:
    classification = ClassificationResult(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="academic",
        reason_code="explicit_cross_domain",
        scores={"policy": 5, "academic": 4, "industry": 0},
    )
    plan = replace(
        build_retrieval_plan(classification),
        global_concurrency_cap=2,
        per_source_timeout_seconds=0.2,
        overall_deadline_seconds=0.8,
    )

    first_wave_ids = [step.source.source_id for step in plan.first_wave_sources]
    active_calls = 0
    max_active_calls = 0
    observed_calls: list[str] = []

    def _mk_adapter(source_id: str) -> Callable[[str], asyncio.Future[list[RetrievalHit]]]:
        async def _adapter(_: str) -> list[RetrievalHit]:
            nonlocal active_calls, max_active_calls
            observed_calls.append(source_id)
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
            try:
                await asyncio.sleep(0.05)
                return [_mk_hit(source_id)]
            finally:
                active_calls -= 1

        return _adapter

    fallback_called = False

    async def _fallback_adapter(_: str) -> list[RetrievalHit]:
        nonlocal fallback_called
        fallback_called = True
        return [_mk_hit("policy_official_web_allowlist_fallback")]

    adapter_registry = {
        source_id: _mk_adapter(source_id) for source_id in first_wave_ids
    }
    adapter_registry["policy_official_web_allowlist_fallback"] = _fallback_adapter

    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="latest policy update",
            adapter_registry=adapter_registry,
        )
    )

    assert max_active_calls == 2
    assert sorted(set(observed_calls)) == sorted(first_wave_ids)
    assert len(observed_calls) <= len(first_wave_ids) * plan.query_variant_budget
    assert "policy_official_web_allowlist_fallback" not in observed_calls
    assert not fallback_called
    assert outcome.status == "success"


def test_run_retrieval_enforces_per_source_timeout() -> None:
    classification = ClassificationResult(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        reason_code="academic_hit",
        scores={"policy": 0, "academic": 5, "industry": 0},
    )
    base_plan = build_retrieval_plan(classification)
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.05,
        overall_deadline_seconds=0.6,
        global_concurrency_cap=1,
    )

    async def _slow_adapter(_: str) -> list[RetrievalHit]:
        await asyncio.sleep(0.5)
        return [_mk_hit(first_step.source.source_id)]

    started_at = time.perf_counter()
    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="recent paper",
            adapter_registry={first_step.source.source_id: _slow_adapter},
        )
    )
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.35
    assert outcome.status == "failure_gaps"
    assert outcome.failure_reason == "timeout"
    assert first_step.source.source_id in outcome.gaps


def test_run_retrieval_overall_deadline_cancel_converges_partial_results() -> None:
    classification = ClassificationResult(
        route_label="mixed",
        primary_route="academic",
        supplemental_route="industry",
        reason_code="explicit_cross_domain",
        scores={"policy": 0, "academic": 5, "industry": 4},
    )
    plan = replace(
        build_retrieval_plan(classification),
        per_source_timeout_seconds=1.0,
        overall_deadline_seconds=0.12,
        global_concurrency_cap=3,
    )

    first_wave_ids = [step.source.source_id for step in plan.first_wave_sources]
    quick_source = "academic_semantic_scholar"
    cancelled_sources: set[str] = set()

    def _mk_slow(source_id: str) -> Callable[[str], asyncio.Future[list[RetrievalHit]]]:
        async def _adapter(_: str) -> list[RetrievalHit]:
            try:
                await asyncio.sleep(1.0)
                return [_mk_hit(source_id)]
            except asyncio.CancelledError:
                cancelled_sources.add(source_id)
                raise

        return _adapter

    async def _quick(_: str) -> list[RetrievalHit]:
        await asyncio.sleep(0.02)
        return [_mk_hit(quick_source)]

    adapter_registry: dict[str, Callable[[str], asyncio.Future[list[RetrievalHit]]]] = {}
    for source_id in first_wave_ids:
        if source_id == quick_source:
            adapter_registry[source_id] = _quick
        else:
            adapter_registry[source_id] = _mk_slow(source_id)

    started_at = time.perf_counter()
    outcome = asyncio.run(
        run_retrieval(
            plan=plan,
            query="multi source",
            adapter_registry=adapter_registry,
        )
    )
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.4
    assert cancelled_sources
    assert any(hit.source_id == quick_source for hit in outcome.results)
    assert outcome.status == "partial"
