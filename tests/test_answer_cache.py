"""Task 5 regressions for stable grounded-answer caching."""

from __future__ import annotations

import asyncio
import json

from skill.api.schema import AnswerResponse, RetrieveResponse
from skill.orchestrator.budget import RuntimeBudget
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.synthesis.cache import ANSWER_CACHE, GroundedAnswerCache
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


def _grounded_answer_response() -> AnswerResponse:
    return AnswerResponse(
        answer_status="grounded_success",
        retrieval_status="success",
        failure_reason=None,
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        conclusion='Closest retained policy match: "Climate Order 2026".',
        key_points=[],
        sources=[],
        uncertainty_notes=[],
        gaps=[],
    )


def _policy_fast_path_retrieve_response() -> RetrieveResponse:
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
        gaps=["Official registry timed out."],
        results=[],
        canonical_evidence=[],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def test_grounded_answer_cache_uses_versioned_normalized_keys() -> None:
    cache_v1 = GroundedAnswerCache(pipeline_version="v1")
    cache_v2 = GroundedAnswerCache(pipeline_version="v2")
    plan = _build_plan("policy", "policy", None)

    cache_v1.put(
        query="latest climate order version",
        plan=plan,
        response=_grounded_answer_response(),
        evidence_token_estimate=8,
        answer_token_estimate=12,
    )

    assert (
        cache_v1.get(
            query="  LATEST   climate ORDER version  ",
            plan=plan,
        )
        is not None
    )
    assert (
        cache_v2.get(
            query="latest climate order version",
            plan=plan,
        )
        is None
    )


def test_execute_answer_pipeline_with_trace_reuses_cached_grounded_success(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    ANSWER_CACHE.clear()
    retrieval_call_count = 0

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _policy_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError("policy fast path should skip model generation")

    try:
        first = asyncio.run(
            execute_answer_pipeline_with_trace(
                plan=_build_plan("policy", "policy", None),
                query="latest climate order version",
                adapter_registry={},
                model_client=_NeverCalledModelClient(),
                runtime_budget=RuntimeBudget(),
            )
        )
        second = asyncio.run(
            execute_answer_pipeline_with_trace(
                plan=_build_plan("policy", "policy", None),
                query="  LATEST   climate ORDER version  ",
                adapter_registry={},
                model_client=_NeverCalledModelClient(),
                runtime_budget=RuntimeBudget(),
            )
        )
    finally:
        ANSWER_CACHE.clear()

    assert retrieval_call_count == 1
    assert first.response.answer_status == "grounded_success"
    assert second.response.answer_status == "grounded_success"
    assert second.runtime_trace.elapsed_ms == 0


def test_execute_answer_pipeline_with_trace_does_not_cache_insufficient_evidence(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    ANSWER_CACHE.clear()
    retrieval_call_count = 0
    model_client = _RecordingModelClient(
        {
            "conclusion": "Weak academic draft.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "Weak academic draft.",
                    "citations": [],
                }
            ],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _academic_partial_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    try:
        for _ in range(2):
            result = asyncio.run(
                execute_answer_pipeline_with_trace(
                    plan=_build_plan("academic", "academic", None),
                    query="grounded search evidence packing paper",
                    adapter_registry={},
                    model_client=model_client,
                    runtime_budget=RuntimeBudget(),
                )
            )
            assert result.response.answer_status == "insufficient_evidence"
    finally:
        ANSWER_CACHE.clear()

    assert retrieval_call_count == 2
    assert model_client.call_count == 2


def test_execute_answer_pipeline_with_trace_does_not_cache_retrieval_failure(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    ANSWER_CACHE.clear()
    retrieval_call_count = 0

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _retrieval_failure_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError("retrieval failure should skip generation")

    try:
        for _ in range(2):
            result = asyncio.run(
                execute_answer_pipeline_with_trace(
                    plan=_build_plan("policy", "policy", None),
                    query="latest climate order version",
                    adapter_registry={},
                    model_client=_NeverCalledModelClient(),
                    runtime_budget=RuntimeBudget(),
                )
            )
            assert result.response.answer_status == "retrieval_failure"
    finally:
        ANSWER_CACHE.clear()

    assert retrieval_call_count == 2
