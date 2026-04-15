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
    cited_evidence_ids: tuple[str, ...] = (),
    focus_evidence_ids: tuple[str, ...] = (),
    strong_local_grounding: bool = False,
) -> tuple[str, ...]:
    """Build deterministic uncertainty notes from observable system state."""
    notes: list[str] = []
    scoped_ids = set(focus_evidence_ids or cited_evidence_ids)
    relevant_policy_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == "policy"
        and (not scoped_ids or record.evidence_id in scoped_ids)
    )
    relevant_academic_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == "academic"
        and (not scoped_ids or record.evidence_id in scoped_ids)
    )
    all_academic_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == "academic"
    )
    relevant_industry_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == "industry"
        and (not scoped_ids or record.evidence_id in scoped_ids)
    )
    all_industry_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == "industry"
    )

    if (evidence_clipped or evidence_pruned) and not strong_local_grounding:
        details: list[str] = []
        if evidence_clipped:
            details.append("bounded evidence was clipped")
        if evidence_pruned:
            details.append("bounded evidence was pruned")
        notes.append(f"Evidence clipped: {', '.join(details)}.")

    if retrieval_status != "success" and gaps:
        notes.append(f"Retrieval gaps: {'; '.join(gaps)}")

    if any(
        (
            record.version_status == "version_missing"
            or record.jurisdiction_status != "observed"
        )
        for record in relevant_policy_records
    ):
        notes.append(
            "Policy metadata incomplete: at least one policy record is missing version or observed jurisdiction metadata."
        )

    if any(
        (
            record.canonical_match_confidence == "heuristic"
            or any(
                variant.canonical_match_confidence == "heuristic"
                for variant in record.linked_variants
            )
        )
        for record in relevant_academic_records
    ):
        notes.append(
            "Academic match heuristic: at least one academic merge relied on heuristic citation matching."
        )

    if not strong_local_grounding and (relevant_academic_records or all_academic_records) and (
        retrieval_status != "success"
        or evidence_clipped
        or evidence_pruned
        or citation_issues
    ):
        notes.append(
            "Academic coverage gap: retained academic evidence may miss corroborating papers, benchmarks, or reviewed versions."
        )

    if not strong_local_grounding and (relevant_industry_records or all_industry_records) and (
        retrieval_status != "success"
        or evidence_clipped
        or evidence_pruned
        or citation_issues
    ):
        notes.append(
            "Industry coverage gap: retained industry evidence may miss corroborating filings, official disclosures, or full article-body context."
        )

    if citation_issues:
        notes.append(f"Citation validation: {'; '.join(citation_issues)}")

    return tuple(notes)
