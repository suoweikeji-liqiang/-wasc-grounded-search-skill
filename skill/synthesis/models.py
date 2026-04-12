"""Contracts for grounded structured answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AnswerStatus = Literal["grounded_success", "insufficient_evidence", "retrieval_failure"]


@dataclass(frozen=True)
class ClaimCitation:
    evidence_id: str
    source_record_id: str
    source_url: str
    quote_text: str


@dataclass(frozen=True)
class KeyPoint:
    key_point_id: str
    statement: str
    citations: list[ClaimCitation]


@dataclass(frozen=True)
class SourceReference:
    evidence_id: str
    title: str
    url: str


@dataclass(frozen=True)
class StructuredAnswerDraft:
    conclusion: str
    key_points: list[KeyPoint]
    sources: list[SourceReference]
    uncertainty_notes: list[str]
    gaps: list[str]
