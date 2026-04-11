"""Phase 2 retrieval fallback contract tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from skill.api.schema import RetrieveOutcome
from skill.config.retrieval import DOMAIN_FIRST_WAVE_SOURCES, SOURCE_BACKUP_CHAIN
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
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
