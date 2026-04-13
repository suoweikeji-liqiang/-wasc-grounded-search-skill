"""Phase 4 answer orchestration regressions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from skill.api.schema import RetrieveResponse
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.synthesis.orchestrate import execute_answer_pipeline

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "answer_phase4_cases.json"


class _FakeModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call_count = 0

    def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return json.dumps(self.payload)


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_plan(route_label: str, primary_route: str, supplemental_route: str | None):
    return build_retrieval_plan(
        ClassificationResult(
            route_label=route_label,
            primary_route=primary_route,
            supplemental_route=supplemental_route,
            reason_code=f"{route_label}_keywords",
            scores={"policy": 1, "industry": 1, "academic": 1},
        )
    )


def _grounded_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "Climate Order 2026",
                "canonical_url": "https://www.gov.cn/policy/climate-order-2026",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "The Climate Order takes effect on May 1, 2026.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "policy-2",
                "domain": "policy",
                "canonical_title": "Implementation Bulletin",
                "canonical_url": "https://www.mee.gov.cn/policy/implementation-bulletin",
                "route_role": "primary",
                "authority": "Ministry of Ecology and Environment",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-04-10",
                "effective_date": None,
                "version": "2026-04 notice",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Provincial reporting begins within 30 days of effectiveness.",
                        "source_record_id": "policy-2-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _academic_partial_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        browser_automation="disabled",
        status="partial",
        failure_reason=None,
        gaps=["Only one peer-reviewed source was retained."],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "paper-1",
                "domain": "academic",
                "canonical_title": "Grounded Search Evidence Packing",
                "canonical_url": "https://doi.org/10.1000/evidence-packing",
                "route_role": "primary",
                "evidence_level": "peer_reviewed",
                "canonical_match_confidence": "heuristic",
                "doi": "10.1000/evidence-packing",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "retained_slices": [
                    {
                        "text": "The paper proposes evidence packing with bounded context windows.",
                        "source_record_id": "paper-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=True,
        evidence_pruned=False,
    )


def _retrieval_failure_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="failure_gaps",
        failure_reason="timeout",
        gaps=["Official registry timed out.", "Fallback web allowlist returned no usable hits."],
        results=[],
        canonical_evidence=[],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def test_execute_answer_pipeline_returns_grounded_success_with_cited_key_points(monkeypatch) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    cases = _load_cases()
    model_client = _FakeModelClient(cases["grounded_policy_success"]["answer"])

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    response = asyncio.run(
        execute_answer_pipeline(
            plan=_build_plan("policy", "policy", None),
            query="climate takes effect on May 1",
            adapter_registry={},
            model_client=model_client,
        )
    )

    assert model_client.call_count == 1
    assert response.answer_status == "grounded_success"
    assert len(response.key_points) == 2
    assert len(response.sources) == 2
    assert response.key_points[0].citations[0].source_record_id == "policy-1-slice-1"
    assert response.uncertainty_notes == []


def test_execute_answer_pipeline_downgrades_to_insufficient_evidence_on_citation_failures(monkeypatch) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    cases = _load_cases()
    model_client = _FakeModelClient(cases["academic_insufficient_evidence"]["answer"])

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _academic_partial_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    response = asyncio.run(
        execute_answer_pipeline(
            plan=_build_plan("academic", "academic", None),
            query=cases["academic_insufficient_evidence"]["query"],
            adapter_registry={},
            model_client=model_client,
        )
    )

    assert response.answer_status == "insufficient_evidence"
    assert len(response.key_points) == 1
    assert len(response.sources) == 1
    assert any(note.startswith("Evidence clipped:") for note in response.uncertainty_notes)
    assert any(note.startswith("Retrieval gaps:") for note in response.uncertainty_notes)
    assert any(note.startswith("Academic match heuristic:") for note in response.uncertainty_notes)
    assert any(note.startswith("Citation validation:") for note in response.uncertainty_notes)


def test_execute_answer_pipeline_skips_model_call_on_retrieval_failure(monkeypatch) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    model_client = _FakeModelClient({"conclusion": "should not be used"})

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _retrieval_failure_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    response = asyncio.run(
        execute_answer_pipeline(
            plan=_build_plan("policy", "policy", None),
            query="latest methane registry update",
            adapter_registry={},
            model_client=model_client,
        )
    )

    assert model_client.call_count == 0
    assert response.answer_status == "retrieval_failure"
    assert response.conclusion == "Retrieval failed before a grounded answer could be produced."
    assert response.key_points == []
    assert response.sources == []
    assert response.gaps
