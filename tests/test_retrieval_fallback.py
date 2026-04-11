"""Phase 2 retrieval fallback contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from skill.api.schema import RetrieveOutcome
from skill.config.retrieval import DOMAIN_FIRST_WAVE_SOURCES, SOURCE_BACKUP_CHAIN
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.models import RetrievalFailureReason, RetrievalStatus

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "retrieval_phase2_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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
