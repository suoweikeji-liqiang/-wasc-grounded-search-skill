"""Phase 5 runtime budget contract regressions."""

from __future__ import annotations

from dataclasses import fields

from skill.config.retrieval import OVERALL_RETRIEVAL_DEADLINE_SECONDS
from skill.retrieval.orchestrate import DEFAULT_EVIDENCE_TOKEN_BUDGET


def test_runtime_budget_defaults_match_phase_5_contract(monkeypatch) -> None:
    monkeypatch.delenv("WASC_REQUEST_DEADLINE_SECONDS", raising=False)
    monkeypatch.delenv("WASC_SYNTHESIS_DEADLINE_SECONDS", raising=False)
    monkeypatch.delenv("WASC_ANSWER_TOKEN_BUDGET", raising=False)

    from skill.orchestrator.budget import RuntimeBudget

    budget = RuntimeBudget.from_env()

    assert budget.request_deadline_seconds == 10.0
    assert budget.retrieval_deadline_seconds == OVERALL_RETRIEVAL_DEADLINE_SECONDS
    assert budget.synthesis_deadline_seconds == 3.0
    assert budget.evidence_token_budget == DEFAULT_EVIDENCE_TOKEN_BUDGET
    assert budget.answer_token_budget == 1200


def test_runtime_budget_reads_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("WASC_REQUEST_DEADLINE_SECONDS", "9.5")
    monkeypatch.setenv("WASC_SYNTHESIS_DEADLINE_SECONDS", "1.75")
    monkeypatch.setenv("WASC_ANSWER_TOKEN_BUDGET", "900")

    from skill.orchestrator.budget import RuntimeBudget

    budget = RuntimeBudget.from_env()

    assert budget.request_deadline_seconds == 9.5
    assert budget.retrieval_deadline_seconds == OVERALL_RETRIEVAL_DEADLINE_SECONDS
    assert budget.synthesis_deadline_seconds == 1.75
    assert budget.evidence_token_budget == DEFAULT_EVIDENCE_TOKEN_BUDGET
    assert budget.answer_token_budget == 900


def test_runtime_budget_calculates_remaining_request_and_synthesis_budget() -> None:
    from skill.orchestrator.budget import RuntimeBudget

    budget = RuntimeBudget(
        request_deadline_seconds=8.0,
        retrieval_deadline_seconds=6.0,
        synthesis_deadline_seconds=2.0,
        evidence_token_budget=48,
        answer_token_budget=1200,
    )

    assert budget.remaining_request_seconds(elapsed_seconds=3.5) == 4.5
    assert budget.remaining_synthesis_seconds(retrieval_elapsed_seconds=5.25) == 2.0
    assert budget.remaining_synthesis_seconds(retrieval_elapsed_seconds=6.8) == 1.2
    assert budget.remaining_synthesis_seconds(retrieval_elapsed_seconds=8.2) == 0.0


def test_runtime_trace_and_answer_execution_result_publish_required_fields() -> None:
    from skill.orchestrator.budget import AnswerExecutionResult, RuntimeTrace

    trace_fields = {field.name for field in fields(RuntimeTrace)}
    result_fields = {field.name for field in fields(AnswerExecutionResult)}

    assert trace_fields == {
        "request_id",
        "route_label",
        "answer_status",
        "retrieval_status",
        "elapsed_ms",
        "retrieval_elapsed_ms",
        "synthesis_elapsed_ms",
        "evidence_token_estimate",
        "answer_token_estimate",
        "latency_budget_ok",
        "token_budget_ok",
        "failure_reason",
        "budget_exhausted_phase",
        "provider_prompt_tokens",
        "provider_completion_tokens",
        "provider_total_tokens",
        "retrieval_trace",
    }
    assert result_fields == {"response", "runtime_trace"}
