"""Retrieval contracts used by the planner and API layer."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    authority: str | None = None
    jurisdiction: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    version: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None
    evidence_level: str | None = None
    target_route: str | None = None
    variant_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    variant_queries: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.credibility_tier is None:
            derived = derive_credibility_tier(self.source_id)
            if derived is not None:
                object.__setattr__(self, "credibility_tier", derived)
        object.__setattr__(self, "variant_reason_codes", tuple(self.variant_reason_codes))
        object.__setattr__(self, "variant_queries", tuple(self.variant_queries))
        if len(self.variant_reason_codes) != len(self.variant_queries):
            raise ValueError(
                "variant_reason_codes and variant_queries must have the same length"
            )


@dataclass(frozen=True)
class SourceExecutionResult:
    source_id: str
    status: RetrievalStatus
    hits: tuple[RetrievalHit, ...] = ()
    failure_reason: RetrievalFailureReason | None = None
    gaps: tuple[str, ...] = ()
    stage: str = "first_wave"
    started_at_ms: int = 0
    elapsed_ms: int = 0
    error_class: str = "ok"
    was_cancelled_by_deadline: bool = False
