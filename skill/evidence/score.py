"""Deterministic scoring for canonical evidence records."""

from __future__ import annotations

from dataclasses import replace

from skill.evidence.models import CanonicalEvidence, EvidenceSlice

_ROUTE_ROLE_SCORES = {
    "primary": 8.0,
    "supplemental": 3.5,
}

_CREDIBILITY_SCORES = {
    "official_government": 7.0,
    "peer_reviewed": 6.0,
    "company_official": 4.0,
    "trusted_news": 3.5,
    "industry_news": 2.5,
}

_EVIDENCE_LEVEL_SCORES = {
    "peer_reviewed": 3.0,
    "survey_or_review": 2.5,
    "preprint": 1.5,
    "metadata_only": 0.5,
}


def _sort_slices(slices: tuple[EvidenceSlice, ...]) -> tuple[EvidenceSlice, ...]:
    return tuple(
        sorted(
            slices,
            key=lambda slice_: (-slice_.score, slice_.token_estimate, slice_.text),
        )
    )


def _completeness_score(record: CanonicalEvidence) -> float:
    score = 0.0
    if record.authority:
        score += 2.5
    if record.publication_date:
        score += 1.5
    if record.effective_date:
        score += 1.0
    if record.version_status == "observed":
        score += 1.5
    elif record.version_status == "version_missing":
        score += 0.25
    if record.jurisdiction_status == "observed":
        score += 1.0
    elif record.jurisdiction_status == "jurisdiction_inferred":
        score += 0.5
    if record.linked_variants:
        score += 0.5
    return score


def _authority_score(record: CanonicalEvidence) -> float:
    score = _CREDIBILITY_SCORES.get(record.raw_records[0].credibility_tier or "", 0.0)
    score += _EVIDENCE_LEVEL_SCORES.get(record.evidence_level or "", 0.0)
    if record.canonical_match_confidence == "strong_id":
        score += 1.0
    elif record.canonical_match_confidence == "heuristic":
        score += 0.25
    return score


def _slice_score(record: CanonicalEvidence) -> float:
    return sum(slice_.score * 4.0 for slice_ in record.retained_slices)


def _with_total_score(record: CanonicalEvidence, *, total_score: float) -> CanonicalEvidence:
    sorted_record = replace(
        record,
        retained_slices=_sort_slices(record.retained_slices),
        token_estimate=sum(slice_.token_estimate for slice_ in record.retained_slices),
    )
    object.__setattr__(sorted_record, "total_score", round(total_score, 6))
    return sorted_record


def _score_record(record: CanonicalEvidence) -> float:
    return (
        _ROUTE_ROLE_SCORES.get(record.route_role, 0.0)
        + _completeness_score(record)
        + _authority_score(record)
        + _slice_score(record)
    )


def score_evidence_records(records: list[CanonicalEvidence]) -> list[CanonicalEvidence]:
    """Score and deterministically order canonical evidence records."""

    scored = [_with_total_score(record, total_score=_score_record(record)) for record in records]
    return sorted(
        scored,
        key=lambda record: (
            -getattr(record, "total_score", 0.0),
            record.route_role != "primary",
            record.evidence_id,
        ),
    )
