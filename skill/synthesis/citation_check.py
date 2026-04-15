"""Fail-closed citation validation for grounded answers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

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


def _normalize_quote_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = "".join(
        " " if unicodedata.category(character).startswith(("P", "S")) else character
        for character in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


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
        validated_citations = []
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

            quote_text = citation.quote_text.strip()
            if quote_text:
                normalized_quote = _normalize_quote_text(quote_text)
                normalized_slice = _normalize_quote_text(slice_text)
                if (
                    citation.quote_text != slice_text
                    and citation.quote_text not in slice_text
                    and normalized_quote != normalized_slice
                    and normalized_quote not in normalized_slice
                ):
                    issues.append(
                        f"{key_point.key_point_id}: quote_text mismatch for {citation.source_record_id}"
                    )
                    point_valid = False
                    continue

            validated_citations.append(
                replace(
                    citation,
                    source_url=record.canonical_url,
                    quote_text=slice_text,
                )
            )

        if point_valid:
            validated_key_points.append(replace(key_point, citations=validated_citations))

    return CitationCheckResult(
        validated_key_points=tuple(validated_key_points),
        issues=tuple(issues),
        grounded_key_point_count=len(validated_key_points),
        total_key_point_count=len(draft.key_points),
    )
