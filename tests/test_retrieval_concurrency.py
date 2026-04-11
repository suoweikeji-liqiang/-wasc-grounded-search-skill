"""Phase 2 retrieval planning contract tests for first-wave fan-out behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill.config.retrieval import (
    DOMAIN_FIRST_WAVE_SOURCES,
    GLOBAL_CONCURRENCY_CAP,
    OVERALL_RETRIEVAL_DEADLINE_SECONDS,
    PER_SOURCE_TIMEOUT_SECONDS,
)
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "retrieval_phase2_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _source_ids_for(plan: Any, *, route: str, supplemental_only: bool) -> list[str]:
    return [
        step.source.source_id
        for step in plan.first_wave_sources
        if step.source.route == route and step.source.is_supplemental == supplemental_only
    ]


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
