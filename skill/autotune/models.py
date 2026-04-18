"""Structured models for autotune round state."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionOutcome = Literal["pending", "baseline", "kept", "reverted", "rejected"]


class BenchmarkSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_dir: Path
    summary_path: Path
    grounded_success: float | None = Field(default=None, ge=0.0, le=1.0)


class JudgeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_dir: Path
    scores_dir: Path
    summary_path: Path
    aggregate_score: float | None = Field(default=None, ge=0.0, le=1.0)
    total_scores: int = Field(default=0, ge=0)


class DecisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: DecisionOutcome = "pending"
    reason: str = ""


class RoundMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    cases_path: Path
    benchmark: BenchmarkSnapshot
    judge: JudgeSnapshot
    decision: DecisionSnapshot = Field(default_factory=DecisionSnapshot)
