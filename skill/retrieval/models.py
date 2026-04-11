"""Retrieval contracts used by the planner and API layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from skill.config.retrieval import SOURCE_CREDIBILITY_TIERS

RetrievalStatus = Literal["success", "partial", "failure_gaps"]
RetrievalFailureReason = Literal["no_hits", "timeout", "rate_limited", "adapter_error"]


def derive_credibility_tier(source_id: str) -> str | None:
    """Derive a deterministic credibility tier from source ID mapping."""
    return SOURCE_CREDIBILITY_TIERS.get(source_id)


@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    title: str
    url: str
    snippet: str
    credibility_tier: str | None = None

    def __post_init__(self) -> None:
        if self.credibility_tier is None:
            derived = derive_credibility_tier(self.source_id)
            if derived is not None:
                object.__setattr__(self, "credibility_tier", derived)


@dataclass(frozen=True)
class SourceExecutionResult:
    source_id: str
    status: RetrievalStatus
    hits: tuple[RetrievalHit, ...] = ()
    failure_reason: RetrievalFailureReason | None = None
    gaps: tuple[str, ...] = ()
