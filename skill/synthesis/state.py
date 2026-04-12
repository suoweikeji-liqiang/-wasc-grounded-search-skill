"""Deterministic final answer-state mapping."""

from __future__ import annotations

from skill.synthesis.models import AnswerStatus


def determine_answer_status(
    *,
    retrieval_status: str,
    failure_reason: str | None,
    canonical_evidence_count: int,
    grounded_key_point_count: int,
    total_key_point_count: int,
) -> AnswerStatus:
    """Map retrieval and grounding results into the Phase 4 answer states."""
    if retrieval_status == "failure_gaps" and canonical_evidence_count == 0:
        return "retrieval_failure"
    if canonical_evidence_count == 0:
        return "insufficient_evidence"
    if total_key_point_count == 0:
        return "insufficient_evidence"
    if grounded_key_point_count < total_key_point_count:
        return "insufficient_evidence"
    return "grounded_success"
