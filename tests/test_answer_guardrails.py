"""Task 4 regressions for local-first answer guardrails."""

from __future__ import annotations

import asyncio
import json

from skill.api.schema import RetrieveResponse
from skill.orchestrator.budget import RuntimeBudget
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace


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


class _RecordingModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call_count = 0

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        self.call_count += 1
        return json.dumps(self.payload)


def _policy_guardrail_retrieve_response() -> RetrieveResponse:
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
                        "text": "The Climate Order 2026 takes effect on May 1, 2026.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=True,
        evidence_pruned=False,
    )


def _mixed_guardrail_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=["supplemental evidence set was narrowed during retrieval"],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "State Council autonomous driving pilot regulation",
                "canonical_url": "https://www.gov.cn/policy/autonomous-driving",
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
                        "text": "Autonomous driving pilot regulation updates 2026 compliance requirements.",
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
                        "text": "Suppliers expect autonomous driving regulation to increase industry investment in 2026.",
                        "source_record_id": "industry-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def test_answer_pipeline_falls_back_to_local_candidate_when_model_drops_effective_date(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _policy_guardrail_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "Closest retained policy match: Official bulletin.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The policy remains active.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order 2026 takes effect on May 1, 2026.",
                        }
                    ],
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "Climate Order 2026",
                    "url": "https://www.gov.cn/policy/climate-order-2026",
                }
            ],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="latest climate order version effective date",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 1
    assert result.response.answer_status == "grounded_success"
    assert "Climate Order 2026" in result.response.conclusion
    assert "2026-04 edition" in result.response.conclusion
    assert "2026-05-01" in result.response.conclusion


def test_answer_pipeline_falls_back_to_local_candidate_when_model_weakens_mixed_route_coverage(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _mixed_guardrail_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "Autonomous driving policy is tightening in 2026.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "Autonomous driving pilot regulation updates 2026 compliance requirements.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/autonomous-driving",
                            "quote_text": "Autonomous driving pilot regulation updates 2026 compliance requirements.",
                        }
                    ],
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "State Council autonomous driving pilot regulation",
                    "url": "https://www.gov.cn/policy/autonomous-driving",
                }
            ],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query="autonomous driving policy impact on industry",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 1
    assert result.response.answer_status == "grounded_success"
    assert "State Council autonomous driving pilot regulation" in result.response.conclusion
    assert "BYD autonomous driving supplier investment update" in result.response.conclusion
    assert len(result.response.sources) == 2
