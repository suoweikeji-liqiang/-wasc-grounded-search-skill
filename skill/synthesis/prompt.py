"""Prompt construction for grounded structured answers."""

from __future__ import annotations

import json

from skill.evidence.models import CanonicalEvidence


def _serialize_evidence(record: CanonicalEvidence) -> dict[str, object]:
    return {
        "evidence_id": record.evidence_id,
        "domain": record.domain,
        "canonical_title": record.canonical_title,
        "canonical_url": record.canonical_url,
        "route_role": record.route_role,
        "authority": record.authority,
        "jurisdiction": record.jurisdiction,
        "jurisdiction_status": record.jurisdiction_status,
        "publication_date": record.publication_date,
        "effective_date": record.effective_date,
        "version": record.version,
        "version_status": record.version_status,
        "evidence_level": record.evidence_level,
        "canonical_match_confidence": record.canonical_match_confidence,
        "doi": record.doi,
        "arxiv_id": record.arxiv_id,
        "first_author": record.first_author,
        "year": record.year,
        "retained_slices": [
            {
                "source_record_id": slice_.source_record_id,
                "text": slice_.text,
                "source_span": slice_.source_span,
            }
            for slice_ in record.retained_slices
        ],
    }


def build_grounded_answer_prompt(
    query: str,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    evidence_clipped: bool,
    evidence_pruned: bool,
    retrieval_gaps: tuple[str, ...],
) -> str:
    """Serialize bounded evidence into a strict JSON-only synthesis prompt."""
    evidence_blob = json.dumps(
        [_serialize_evidence(record) for record in canonical_evidence],
        ensure_ascii=True,
        indent=2,
    )
    gaps_blob = json.dumps(list(retrieval_gaps), ensure_ascii=True)
    clipped_value = "true" if evidence_clipped else "false"
    pruned_value = "true" if evidence_pruned else "false"
    return (
        "You are a grounded answer generator.\n"
        "Return JSON only with fields conclusion, key_points, sources, uncertainty_notes.\n"
        "Each key_points item must contain key_point_id, statement, citations.\n"
        "Each citation must contain evidence_id, source_record_id, source_url, quote_text.\n"
        f"query: {query}\n"
        f"evidence_clipped: {clipped_value}\n"
        f"evidence_pruned: {pruned_value}\n"
        f"retrieval_gaps: {gaps_blob}\n"
        "canonical_evidence:\n"
        f"{evidence_blob}\n"
    )
