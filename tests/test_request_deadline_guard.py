"""Hard-cap regression for execute_answer_pipeline_with_trace.

The pipeline must return a retrieval_failure with failure_reason=timeout
when internal retrieval/synthesis hangs past request_deadline_seconds +
the small grace buffer. Without this guard, a non-cancellable adapter
could block the process until an external subprocess kill (e.g. the
benchmark harness's 60s ceiling).
"""

from __future__ import annotations

import asyncio

from skill.api.schema import RetrieveResponse
from skill.orchestrator.budget import RuntimeBudget
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace


def _build_plan(route_label: str, primary_route: str):
    return build_retrieval_plan(
        ClassificationResult(
            route_label=route_label,
            primary_route=primary_route,
            supplemental_route=None,
            reason_code=f"{route_label}_keywords",
            scores={"policy": 1, "industry": 1, "academic": 1},
        )
    )


class _NeverCalledModelClient:
    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        raise AssertionError("synthesis must not run when retrieval hangs")


def test_hard_cap_triggers_retrieval_failure_on_hung_retrieval(monkeypatch) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _hanging_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        await asyncio.sleep(30.0)
        raise AssertionError("hung retrieval should have been cancelled")

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _hanging_execute_retrieval_pipeline,
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("industry", "industry"),
            query="hung industry query",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(request_deadline_seconds=0.3),
        )
    )

    assert result.response.answer_status == "retrieval_failure"
    assert result.response.failure_reason == "timeout"
    assert result.runtime_trace.budget_exhausted_phase == "request"
    # Guard fires at request_deadline + grace (default 1.5s); allow a small buffer.
    assert result.runtime_trace.elapsed_ms < 5_000


def test_hard_cap_does_not_fire_when_pipeline_returns_fast(monkeypatch) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate

    async def _fast_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return RetrieveResponse(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            status="failure_gaps",
            failure_reason="no_hits",
            gaps=["policy_official_registry"],
            results=[],
            canonical_evidence=[],
            evidence_clipped=False,
            evidence_pruned=False,
        )

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fast_execute_retrieval_pipeline,
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy"),
            query="fast policy query",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(request_deadline_seconds=1.0),
        )
    )

    # No hang, so the normal retrieval_failure path ran; guard stayed silent.
    assert result.runtime_trace.budget_exhausted_phase != "request"
