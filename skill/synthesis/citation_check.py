"""Fail-closed citation validation for grounded answers."""

from __future__ import annotations

from dataclasses import dataclass

from skill.evidence.models import CanonicalEvidence
from skill.synthesis.models import KeyPoint, StructuredAnswerDraft


@dataclass(frozen=True)
class CitationCheckResult:
    validated_key_points: tuple[KeyPoint, ...]
    issues: tuple[str, ...]
    grounded_key_point_count: int
    total_key_point_count: int


def _slice_text_by_source_id(record: CanonicalEvidence) -> dict[str, str]:
    return {slice_.source_record_id: slice_.text for slice_ in record.retained_slices}


def validate_answer_citations(
    draft: StructuredAnswerDraft,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> CitationCheckResult:
    """Validate key-point citations against evidence IDs and retained-slice text."""
    evidence_index = {record.evidence_id: record for record in canonical_evidence}
    validated_key_points: list[KeyPoint] = []
    issues: list[str] = []

    for key_point in draft.key_points:
        if not key_point.citations:
            issues.append(f"{key_point.key_point_id}: missing citations")
            continue

        point_valid = True
        for citation in key_point.citations:
            record = evidence_index.get(citation.evidence_id)
            if record is None:
                issues.append(f"{key_point.key_point_id}: missing evidence_id {citation.evidence_id}")
                point_valid = False
                continue

            slice_index = _slice_text_by_source_id(record)
            slice_text = slice_index.get(citation.source_record_id)
            if slice_text is None:
                issues.append(
                    f"{key_point.key_point_id}: missing source_record_id {citation.source_record_id}"
                )
                point_valid = False
                continue

            if citation.quote_text != slice_text and citation.quote_text not in slice_text:
                issues.append(
                    f"{key_point.key_point_id}: quote_text mismatch for {citation.source_record_id}"
                )
                point_valid = False

        if point_valid:
            validated_key_points.append(key_point)

    return CitationCheckResult(
        validated_key_points=tuple(validated_key_points),
        issues=tuple(issues),
        grounded_key_point_count=len(validated_key_points),
        total_key_point_count=len(draft.key_points),
    )
