"""Phase 5 answer-runtime budget regressions."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from skill.api.schema import RetrieveResponse
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import run_retrieval
from skill.retrieval.models import RetrievalHit


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
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


class _RecordingModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call_count = 0
        self.timeouts: list[float | None] = []

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        self.call_count += 1
        self.timeouts.append(timeout_seconds)
        return json.dumps(self.payload)


def test_execute_answer_pipeline_with_trace_forwards_remaining_synthesis_timeout(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "The Climate Order takes effect on May 1, 2026.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
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
            query="latest climate order version",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 1
    assert model_client.timeouts[0] is not None
    assert 1.5 <= model_client.timeouts[0] <= 2.0
    assert result.response.answer_status == "grounded_success"
    assert result.runtime_trace.latency_budget_ok is True
    assert result.runtime_trace.token_budget_ok is True
    assert result.runtime_trace.evidence_token_estimate > 0
    assert result.runtime_trace.answer_token_estimate is not None


def test_execute_answer_pipeline_with_trace_enforces_answer_token_budget(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": (
                "The Climate Order takes effect on May 1, 2026 and applies "
                "across the full reporting window with additional obligations."
            ),
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
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
            query="latest climate order version",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(answer_token_budget=3),
        )
    )

    assert model_client.call_count == 1
    assert result.response.answer_status == "insufficient_evidence"
    assert (
        result.response.conclusion
        == "Available runtime budget was insufficient to complete grounded synthesis."
    )
    assert any(
        note.startswith("Budget enforcement:")
        for note in result.response.uncertainty_notes
    )
    assert result.runtime_trace.token_budget_ok is False
    assert result.runtime_trace.budget_exhausted_phase == "answer_tokens"


def test_execute_answer_pipeline_with_trace_skips_generation_for_irrelevant_evidence(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="battery recycling market share 2025",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.key_points == []
    assert result.response.sources == []
    assert any(
        note.startswith("Relevance gate:")
        for note in result.response.uncertainty_notes
    )
    assert result.runtime_trace.budget_exhausted_phase is None
    assert result.runtime_trace.latency_budget_ok is True


def test_run_retrieval_propagates_cancelled_error() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 4, "academic": 0, "industry": 0},
    )
    base_plan = build_retrieval_plan(classification)
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.5,
        overall_deadline_seconds=0.5,
        global_concurrency_cap=1,
    )

    async def _cancelled(_: str) -> list[RetrievalHit]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_retrieval(
                plan=plan,
                query="latest climate order version",
                adapter_registry={first_step.source.source_id: _cancelled},
            )
        )


def test_answer_endpoint_stores_runtime_trace_and_omits_internal_budget_fields(
    monkeypatch,
) -> None:
    import skill.api.entry as api_entry

    monkeypatch.setenv("WASC_SYNTHESIS_DEADLINE_SECONDS", "0")

    def _unexpected_default_adapter_registry() -> dict[str, object]:
        raise AssertionError("default adapter registry should not be used")

    async def _policy_adapter(_: str) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                source_id="policy_official_registry",
                title="Climate Order 2026",
                url="https://www.gov.cn/policy/climate-order-2026",
                snippet="The Climate Order takes effect on May 1, 2026.",
                authority="State Council",
                jurisdiction="CN",
                publication_date="2026-04-01",
                effective_date="2026-05-01",
                version="2026-04 edition",
            )
        ]

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError("budget exhaustion should skip grounded synthesis")

    monkeypatch.setattr(
        api_entry,
        "_default_adapter_registry",
        _unexpected_default_adapter_registry,
    )
    monkeypatch.setattr(
        api_entry,
        "classify_query",
        lambda _query: ClassificationResult(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            reason_code="policy_hit",
            scores={"policy": 4, "academic": 0, "industry": 0},
        ),
    )

    api_entry.app.state.adapter_registry = {
        "policy_official_registry": _policy_adapter,
    }
    api_entry.app.state.model_client = _NeverCalledModelClient()

    try:
        client = TestClient(api_entry.app)
        response = client.post(
            "/answer",
            json={"query": "latest climate order version"},
        )
    finally:
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_status"] == "insufficient_evidence"
    assert any(
        note.startswith("Budget enforcement:")
        for note in payload["uncertainty_notes"]
    )
    assert "runtime_trace" not in payload
    assert "latency_budget_ok" not in payload
    assert "token_budget_ok" not in payload
    assert "evidence_token_estimate" not in payload
    assert "answer_token_estimate" not in payload

    runtime_trace = api_entry.app.state.last_runtime_trace
    assert runtime_trace.route_label == "policy"
    assert runtime_trace.answer_status == "insufficient_evidence"
    assert runtime_trace.budget_exhausted_phase == "synthesis"
    assert runtime_trace.evidence_token_estimate > 0
