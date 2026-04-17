"""Regressions for scoring partial evidence without blank answers."""

from __future__ import annotations

import asyncio
import json

from skill.api.schema import RetrieveResponse
from skill.orchestrator.budget import RuntimeBudget
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.synthesis.generator import ModelBackendError
from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace


class _FakeModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call_count = 0

    def generate_text(
        self,
        prompt: str,
        timeout_seconds: float | None = None,
    ) -> str:
        del prompt, timeout_seconds
        self.call_count += 1
        return json.dumps(self.payload)


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


_PARTIAL_MIXED_QUERY = "autonomous driving regulation supplier investment costs"
_ACADEMIC_LOOKUP_QUERY = "\u6709\u54ea\u4e9b grounded search evidence packing \u8bba\u6587"


def _partial_mixed_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        browser_automation="disabled",
        status="partial",
        failure_reason="timeout",
        gaps=["industry_web_discovery"],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "State Council autonomous driving pilot regulation",
                "canonical_url": "https://www.gov.cn/zhengce/autonomous-driving-pilot-regulation",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-03-28",
                "effective_date": "2026-05-01",
                "version": "2026 pilot edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Official autonomous driving pilot regulation sets 2026 compliance requirements for road testing.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "industry-1",
                "domain": "industry",
                "canonical_title": "BYD autonomous driving supplier investment update",
                "canonical_url": "https://www.byd.com/news/autonomous-driving-supplier-investment-2026",
                "route_role": "supplemental",
                "retained_slices": [
                    {
                        "text": "Company update says autonomous driving programs are increasing supplier investment across the vehicle industry in 2026.",
                        "source_record_id": "industry-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=True,
        evidence_pruned=False,
    )


def _academic_no_support_retrieve_response(
    *,
    failure_reason: str = "timeout",
) -> RetrieveResponse:
    return RetrieveResponse(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        browser_automation="disabled",
        status="failure_gaps",
        failure_reason=failure_reason,
        gaps=[
            "academic_semantic_scholar",
            "academic_arxiv",
            "academic_asta_mcp",
        ],
        results=[],
        canonical_evidence=[],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def test_partial_insufficient_evidence_keeps_grounded_conclusion_key_points_and_sources(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _partial_mixed_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _FakeModelClient(
        {
                "conclusion": (
                    "The retained evidence confirms a 2026 autonomous driving pilot regulation and "
                    "separate supplier investment activity, but it does not fully establish the size "
                    "of the cost impact."
                ),
                "key_points": [
                    {
                        "key_point_id": "kp-1",
                    "statement": "Official autonomous driving pilot regulation sets 2026 compliance requirements for road testing.",
                        "citations": [
                            {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            }
                        ],
                    },
                    {
                        "key_point_id": "kp-2",
                    "statement": "The draft also claims quantified supplier cost increases across OEM programs.",
                        "citations": [],
                    },
                ],
                "sources": [
                    {
                    "evidence_id": "policy-1",
                    "title": "State Council autonomous driving pilot regulation",
                    "url": "https://www.gov.cn/zhengce/autonomous-driving-pilot-regulation",
                    }
                ],
                "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query=_PARTIAL_MIXED_QUERY,
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "insufficient_evidence"
    assert "Available evidence was insufficient to fully support" not in result.response.conclusion
    assert "autonomous driving pilot regulation" in result.response.conclusion
    assert "taken together" in result.response.conclusion.lower()
    assert "cautious partial answer" in result.response.conclusion.lower()
    assert "policy-side signal and a same-topic industry-side signal" in (
        result.response.conclusion.lower()
    )
    assert "does not directly show whether" in result.response.conclusion.lower()
    assert len(result.response.key_points) == 2
    assert len(result.response.sources) == 2
    assert result.response.key_points[0].citations[0].evidence_id == "policy-1"
    assert {source.evidence_id for source in result.response.sources} == {
        "policy-1",
        "industry-1",
    }
    assert any(note.startswith("Retrieval gaps:") for note in result.response.uncertainty_notes)
    assert any(note.startswith("Industry coverage gap:") for note in result.response.uncertainty_notes)


def test_generation_backend_failure_with_canonical_evidence_still_returns_partial_facts(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _partial_mixed_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _FailingModelClient:
        def generate_text(
            self,
            prompt: str,
            timeout_seconds: float | None = None,
        ) -> str:
            del prompt, timeout_seconds
            raise ModelBackendError("MiniMax request failed with status 500")

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query=_PARTIAL_MIXED_QUERY,
            adapter_registry={},
            model_client=_FailingModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.key_points
    assert result.response.sources
    assert "autonomous driving pilot regulation" in result.response.conclusion
    assert any(
        note.startswith(("Answer assembly:", "回答生成："))
        for note in result.response.uncertainty_notes
    )
    assert not any("MiniMax" in note for note in result.response.uncertainty_notes)
    assert not any("status 500" in note for note in result.response.uncertainty_notes)


def test_academic_lookup_without_support_returns_insufficient_evidence_not_retrieval_failure(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _academic_no_support_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self,
            prompt: str,
            timeout_seconds: float | None = None,
        ) -> str:
            raise AssertionError(
                "unsupported academic lookup should not invoke grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("academic", "academic", None),
            query=_ACADEMIC_LOOKUP_QUERY,
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.conclusion != "Retrieval failed before a grounded answer could be produced."
    assert result.response.key_points == []
    assert result.response.sources == []
    assert any(
        note.startswith(("Academic lookup:", "学术检索："))
        for note in result.response.uncertainty_notes
    )
    assert any(note.startswith("Retrieval gaps:") for note in result.response.uncertainty_notes)


def test_academic_lookup_adapter_error_without_support_remains_retrieval_failure(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _academic_no_support_retrieve_response(failure_reason="adapter_error")

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self,
            prompt: str,
            timeout_seconds: float | None = None,
        ) -> str:
            raise AssertionError(
                "retrieval failure should not invoke grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("academic", "academic", None),
            query=_ACADEMIC_LOOKUP_QUERY,
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "retrieval_failure"
    assert result.response.conclusion == "Retrieval failed before a grounded answer could be produced."


def test_budget_enforcement_with_canonical_evidence_still_returns_partial_facts(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _partial_mixed_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _FakeModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query=_PARTIAL_MIXED_QUERY,
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(
                request_deadline_seconds=3.0,
                retrieval_deadline_seconds=3.0,
                synthesis_deadline_seconds=0.0,
            ),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.key_points
    assert result.response.sources
    assert "autonomous driving pilot regulation" in result.response.conclusion
    assert "fully grounded synthesis" in result.response.conclusion
    assert not any(
        note.startswith("Budget enforcement:")
        for note in result.response.uncertainty_notes
    )
