"""Deterministic uncertainty-note derivation."""

from __future__ import annotations

from skill.evidence.models import CanonicalEvidence


def build_uncertainty_notes(
    *,
    retrieval_status: str,
    gaps: tuple[str, ...],
    evidence_clipped: bool,
    evidence_pruned: bool,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    citation_issues: tuple[str, ...],
) -> tuple[str, ...]:
    """Build deterministic uncertainty notes from observable system state."""
    notes: list[str] = []

    if evidence_clipped or evidence_pruned:
        details: list[str] = []
        if evidence_clipped:
            details.append("bounded evidence was clipped")
        if evidence_pruned:
            details.append("bounded evidence was pruned")
        notes.append(f"Evidence clipped: {', '.join(details)}.")

    if retrieval_status != "success" and gaps:
        notes.append(f"Retrieval gaps: {'; '.join(gaps)}")

    if any(
        record.domain == "policy"
        and (
            record.version_status == "version_missing"
            or record.jurisdiction_status != "observed"
        )
        for record in canonical_evidence
    ):
        notes.append(
            "Policy metadata incomplete: at least one policy record is missing version or observed jurisdiction metadata."
        )

    if any(
        record.domain == "academic"
        and (
            record.canonical_match_confidence == "heuristic"
            or any(
                variant.canonical_match_confidence == "heuristic"
                for variant in record.linked_variants
            )
        )
        for record in canonical_evidence
    ):
        notes.append(
            "Academic match heuristic: at least one academic merge relied on heuristic citation matching."
        )

    if citation_issues:
        notes.append(f"Citation validation: {'; '.join(citation_issues)}")

    return tuple(notes)
