"""Regressions for provider usage persistence into runtime traces and benchmark artifacts."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI

from skill.api.schema import AnswerRequest, AnswerResponse, RetrieveResponse
from skill.benchmark.harness import run_benchmark_suite
from skill.benchmark.models import BenchmarkCase
from skill.orchestrator.budget import RuntimeBudget, RuntimeTrace
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


def _policy_retrieve_response() -> RetrieveResponse:
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


def test_execute_answer_pipeline_with_trace_persists_provider_usage(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _policy_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _UsageModelClient:
        def __init__(self) -> None:
            self.last_usage = {
                "prompt_tokens": 321,
                "completion_tokens": 123,
                "total_tokens": 444,
            }

        def generate_text(
            self,
            prompt: str,
            timeout_seconds: float | None = None,
        ) -> str:
            del prompt, timeout_seconds
            return json.dumps(
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
            query="how climate order changes supplier reporting cadence",
            adapter_registry={},
            model_client=_UsageModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.runtime_trace.provider_prompt_tokens == 321
    assert result.runtime_trace.provider_completion_tokens == 123
    assert result.runtime_trace.provider_total_tokens == 444


def test_run_benchmark_suite_persists_provider_usage_columns(tmp_path) -> None:
    app = FastAPI()

    @app.post("/answer", response_model=AnswerResponse)
    async def _answer(payload: AnswerRequest) -> AnswerResponse:
        app.state.last_runtime_trace = RuntimeTrace(
            request_id=f"trace-{payload.query}",
            route_label="policy",
            answer_status="grounded_success",
            retrieval_status="success",
            elapsed_ms=100,
            retrieval_elapsed_ms=40,
            synthesis_elapsed_ms=60,
            evidence_token_estimate=24,
            answer_token_estimate=18,
            latency_budget_ok=True,
            token_budget_ok=True,
            failure_reason=None,
            budget_exhausted_phase=None,
            provider_prompt_tokens=321,
            provider_completion_tokens=123,
            provider_total_tokens=444,
            retrieval_trace=(),
        )
        return AnswerResponse(
            answer_status="grounded_success",
            retrieval_status="success",
            failure_reason=None,
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            conclusion=f"Grounded answer for {payload.query}",
            key_points=[],
            sources=[],
            uncertainty_notes=[],
            gaps=[],
        )

    records = run_benchmark_suite(
        app=app,
        cases=[
            BenchmarkCase(
                case_id="policy-1",
                query="latest climate order version",
            )
        ],
        runs=1,
        output_dir=tmp_path,
    )

    record = records[0].model_dump()
    assert record["provider_prompt_tokens"] == 321
    assert record["provider_completion_tokens"] == 123
    assert record["provider_total_tokens"] == 444
