"""Strict benchmark contracts for Phase 5 reporting."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_route: str | None = None


class BenchmarkRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    run_index: int = Field(ge=1)
    query: str = Field(min_length=1)
    route_label: str = Field(min_length=1)
    answer_status: str = Field(min_length=1)
    retrieval_status: str = Field(min_length=1)
    success: bool
    elapsed_ms: int = Field(ge=0)
    evidence_token_estimate: int = Field(ge=0)
    answer_token_estimate: int | None = Field(default=None, ge=0)
    latency_budget_ok: bool
    token_budget_ok: bool
    failure_reason: str | None = None
    provider_prompt_tokens: int | None = Field(default=None, ge=0)
    provider_completion_tokens: int | None = Field(default=None, ge=0)
    provider_total_tokens: int | None = Field(default=None, ge=0)
    retrieval_trace: list[dict[str, object]] = Field(default_factory=list)


class BenchmarkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_runs: int = Field(ge=0)
    successful_runs: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    latency_p50_ms: int = Field(ge=0)
    latency_p95_ms: int = Field(ge=0)
    latency_budget_pass_rate: float = Field(ge=0.0, le=1.0)
    token_budget_pass_rate: float = Field(ge=0.0, le=1.0)
    answer_status_breakdown: dict[str, int]
    failure_reason_breakdown: dict[str, int]
