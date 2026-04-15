"""Request-scoped runtime budget and trace contracts."""

from __future__ import annotations

import os
from dataclasses import dataclass

from skill.api.schema import AnswerResponse
from skill.config.retrieval import OVERALL_RETRIEVAL_DEADLINE_SECONDS
from skill.retrieval.orchestrate import DEFAULT_EVIDENCE_TOKEN_BUDGET

DEFAULT_REQUEST_DEADLINE_SECONDS = 10.0
DEFAULT_SYNTHESIS_DEADLINE_SECONDS = 3.0
DEFAULT_ANSWER_TOKEN_BUDGET = 1200


def _read_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return float(value)


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


@dataclass(frozen=True)
class RuntimeBudget:
    request_deadline_seconds: float = DEFAULT_REQUEST_DEADLINE_SECONDS
    retrieval_deadline_seconds: float = OVERALL_RETRIEVAL_DEADLINE_SECONDS
    synthesis_deadline_seconds: float = DEFAULT_SYNTHESIS_DEADLINE_SECONDS
    evidence_token_budget: int = DEFAULT_EVIDENCE_TOKEN_BUDGET
    answer_token_budget: int = DEFAULT_ANSWER_TOKEN_BUDGET

    @classmethod
    def from_env(cls) -> RuntimeBudget:
        return cls(
            request_deadline_seconds=_read_float_env(
                "WASC_REQUEST_DEADLINE_SECONDS",
                DEFAULT_REQUEST_DEADLINE_SECONDS,
            ),
            synthesis_deadline_seconds=_read_float_env(
                "WASC_SYNTHESIS_DEADLINE_SECONDS",
                DEFAULT_SYNTHESIS_DEADLINE_SECONDS,
            ),
            answer_token_budget=_read_int_env(
                "WASC_ANSWER_TOKEN_BUDGET",
                DEFAULT_ANSWER_TOKEN_BUDGET,
            ),
        )

    def remaining_request_seconds(self, *, elapsed_seconds: float) -> float:
        return round(
            max(0.0, self.request_deadline_seconds - max(0.0, elapsed_seconds)),
            6,
        )

    def remaining_synthesis_seconds(self, *, retrieval_elapsed_seconds: float) -> float:
        return min(
            self.synthesis_deadline_seconds,
            self.remaining_request_seconds(elapsed_seconds=retrieval_elapsed_seconds),
        )


@dataclass(frozen=True)
class RuntimeTrace:
    request_id: str
    route_label: str
    answer_status: str
    retrieval_status: str
    elapsed_ms: int
    retrieval_elapsed_ms: int
    synthesis_elapsed_ms: int
    evidence_token_estimate: int
    answer_token_estimate: int | None
    latency_budget_ok: bool
    token_budget_ok: bool
    failure_reason: str | None
    budget_exhausted_phase: str | None
    provider_prompt_tokens: int | None = None
    provider_completion_tokens: int | None = None
    provider_total_tokens: int | None = None
    retrieval_trace: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class AnswerExecutionResult:
    response: AnswerResponse
    runtime_trace: RuntimeTrace
