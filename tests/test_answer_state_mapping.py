"""Phase 4 answer-state mapping regressions."""

from __future__ import annotations

import json
from pathlib import Path

from skill.synthesis.state import determine_answer_status

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "answer_phase4_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _grounded_key_point_count(case: dict[str, object]) -> int:
    return sum(1 for item in case["answer"]["key_points"] if item["citations"])


def _total_key_point_count(case: dict[str, object]) -> int:
    return len(case["answer"]["key_points"])


def test_grounded_policy_fixture_maps_to_grounded_success() -> None:
    case = _load_cases()["grounded_policy_success"]

    status = determine_answer_status(
        retrieval_status=case["retrieval_status"],
        failure_reason=case["failure_reason"],
        canonical_evidence_count=len(case["canonical_evidence"]),
        grounded_key_point_count=_grounded_key_point_count(case),
        total_key_point_count=_total_key_point_count(case),
    )

    assert status == "grounded_success"


def test_academic_fixture_with_uncited_key_point_maps_to_insufficient_evidence() -> None:
    case = _load_cases()["academic_insufficient_evidence"]

    status = determine_answer_status(
        retrieval_status=case["retrieval_status"],
        failure_reason=case["failure_reason"],
        canonical_evidence_count=len(case["canonical_evidence"]),
        grounded_key_point_count=_grounded_key_point_count(case),
        total_key_point_count=_total_key_point_count(case),
    )

    assert status == "insufficient_evidence"


def test_retrieval_failure_fixture_maps_to_retrieval_failure() -> None:
    case = _load_cases()["retrieval_failure_case"]

    status = determine_answer_status(
        retrieval_status=case["retrieval_status"],
        failure_reason=case["failure_reason"],
        canonical_evidence_count=len(case["canonical_evidence"]),
        grounded_key_point_count=_grounded_key_point_count(case),
        total_key_point_count=_total_key_point_count(case),
    )

    assert status == "retrieval_failure"


def test_missing_grounded_key_points_cannot_be_grounded_success() -> None:
    status = determine_answer_status(
        retrieval_status="success",
        failure_reason=None,
        canonical_evidence_count=2,
        grounded_key_point_count=0,
        total_key_point_count=2,
    )

    assert status == "insufficient_evidence"
