"""Phase 4 answer contract regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill.api.schema import AnswerRequest, AnswerResponse
from skill.synthesis.models import ClaimCitation, KeyPoint, SourceReference, StructuredAnswerDraft

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "answer_phase4_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_phase4_fixture_covers_grounded_insufficient_and_failure_states() -> None:
    cases = _load_cases()

    assert set(cases) == {
        "grounded_policy_success",
        "academic_insufficient_evidence",
        "retrieval_failure_case",
    }
    assert cases["grounded_policy_success"]["answer"]["key_points"][0]["citations"][0]["evidence_id"] == "policy-1"
    assert cases["academic_insufficient_evidence"]["answer"]["key_points"][1]["citations"] == []
    assert cases["retrieval_failure_case"]["failure_reason"] == "timeout"


def test_structured_answer_draft_requires_conclusion_key_points_sources_uncertainty_and_gaps() -> None:
    cases = _load_cases()
    grounded = cases["grounded_policy_success"]["answer"]

    draft = StructuredAnswerDraft(
        conclusion=grounded["conclusion"],
        key_points=[
            KeyPoint(
                key_point_id=item["key_point_id"],
                statement=item["statement"],
                citations=[
                    ClaimCitation(
                        evidence_id=citation["evidence_id"],
                        source_record_id=citation["source_record_id"],
                        source_url=citation["source_url"],
                        quote_text=citation["quote_text"],
                    )
                    for citation in item["citations"]
                ],
            )
            for item in grounded["key_points"]
        ],
        sources=[
            SourceReference(
                evidence_id=item["evidence_id"],
                title=item["title"],
                url=item["url"],
            )
            for item in grounded["sources"]
        ],
        uncertainty_notes=list(grounded["uncertainty_notes"]),
        gaps=list(grounded["gaps"]),
    )

    assert draft.conclusion.startswith("The 2026 Climate Order")
    assert len(draft.key_points) == 2
    assert len(draft.sources) == 2
    assert draft.uncertainty_notes == []
    assert draft.gaps == []


def test_claim_citation_requires_evidence_and_quote_fields() -> None:
    with pytest.raises(TypeError):
        ClaimCitation(  # type: ignore[call-arg]
            evidence_id="policy-1",
            source_record_id="policy-1-slice-1",
            source_url="https://www.gov.cn/policy/climate-order-2026",
        )


def test_answer_response_requires_all_structured_sections_and_forbids_extra_fields() -> None:
    cases = _load_cases()
    grounded = cases["grounded_policy_success"]

    response = AnswerResponse(
        answer_status="grounded_success",
        retrieval_status=grounded["retrieval_status"],
        failure_reason=grounded["failure_reason"],
        route_label=grounded["route_label"],
        primary_route=grounded["primary_route"],
        supplemental_route=grounded["supplemental_route"],
        browser_automation="disabled",
        conclusion=grounded["answer"]["conclusion"],
        key_points=grounded["answer"]["key_points"],
        sources=grounded["answer"]["sources"],
        uncertainty_notes=grounded["answer"]["uncertainty_notes"],
        gaps=grounded["answer"]["gaps"],
    )

    payload = response.model_dump()
    assert payload["answer_status"] == "grounded_success"
    assert payload["conclusion"]
    assert payload["key_points"]
    assert payload["sources"]
    assert payload["uncertainty_notes"] == []
    assert payload["gaps"] == []

    with pytest.raises(Exception):
        AnswerResponse(
            answer_status="grounded_success",
            retrieval_status="success",
            failure_reason=None,
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            conclusion="ok",
            key_points=[],
            sources=[],
            uncertainty_notes=[],
            gaps=[],
            extra_field="forbidden",  # type: ignore[call-arg]
        )


def test_answer_request_reuses_strict_query_validation() -> None:
    request = AnswerRequest(query=" latest climate order ")
    assert request.query == "latest climate order"

    with pytest.raises(ValueError, match="query"):
        AnswerRequest(query="   ")
