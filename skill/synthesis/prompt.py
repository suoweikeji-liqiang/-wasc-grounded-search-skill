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
        "publication_date": record.publication_date,
        "effective_date": record.effective_date,
        "version": record.version,
        "evidence_level": record.evidence_level,
        "doi": record.doi,
        "arxiv_id": record.arxiv_id,
        "first_author": record.first_author,
        "year": record.year,
        "retained_slices": [
            {
                "source_record_id": slice_.source_record_id,
                "text": slice_.text,
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
        separators=(",", ":"),
    )
    gaps_blob = json.dumps(list(retrieval_gaps), ensure_ascii=True)
    clipped_value = "true" if evidence_clipped else "false"
    pruned_value = "true" if evidence_pruned else "false"
    return (
        "You are a grounded answer generator.\n"
        "Return JSON only with fields conclusion, key_points, sources, uncertainty_notes.\n"
        "Each key_points item must contain key_point_id, statement, citations.\n"
        "Each citation must contain evidence_id and source_record_id.\n"
        "source_url and quote_text are optional and will be backfilled from evidence.\n"
        "Preserve concrete entities, years, versions, publication dates, and effective dates when evidence provides them.\n"
        "Do not replace specific titles or grounded dates with generic summaries.\n"
        "For mixed-route evidence, keep both primary and supplemental route coverage when both are supported by evidence.\n"
        "Do not drop a stronger local evidence-backed candidate in favor of a weaker paraphrase.\n"
        f"query: {query}\n"
        f"evidence_clipped: {clipped_value}\n"
        f"evidence_pruned: {pruned_value}\n"
        f"retrieval_gaps: {gaps_blob}\n"
        "canonical_evidence:\n"
        f"{evidence_blob}\n"
    )
