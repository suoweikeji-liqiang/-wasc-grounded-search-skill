"""Academic evidence canonicalization helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from skill.evidence.models import CanonicalEvidence, EvidenceSlice, LinkedVariant, RawEvidenceRecord

_ACADEMIC_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_ACADEMIC_TITLE_NOISE_RE = re.compile(r"\bworking paper\b|\bpreprint\b", re.IGNORECASE)


@dataclass
class _AcademicGroup:
    records: list[RawEvidenceRecord]
    aliases: set[tuple[str, ...]]


def _normalize_academic_text(value: str | None) -> str:
    if not value:
        return ""
    value = _ACADEMIC_TITLE_NOISE_RE.sub("", value)
    normalized = _ACADEMIC_TOKEN_RE.sub(" ", value.lower())
    return " ".join(normalized.split())


def _academic_aliases(record: RawEvidenceRecord) -> set[tuple[str, ...]]:
    aliases: set[tuple[str, ...]] = set()
    if record.doi:
        aliases.add(("doi", record.doi.lower()))
    if record.arxiv_id:
        aliases.add(("arxiv", record.arxiv_id.lower()))
    if record.title and record.first_author and record.year:
        aliases.add(
            (
                "heuristic",
                _normalize_academic_text(record.title),
                _normalize_academic_text(record.first_author),
                str(record.year),
            )
        )
    if not aliases:
        aliases.add(("source", record.source_id, record.url))
    return aliases


def _academic_priority(record: RawEvidenceRecord) -> tuple[int, int, int]:
    evidence_rank = {
        "peer_reviewed": 3,
        "survey_or_review": 2,
        "preprint": 1,
        "metadata_only": 0,
        None: -1,
    }
    return (
        evidence_rank.get(record.evidence_level, -1),
        1 if record.doi else 0,
        1 if record.arxiv_id else 0,
    )


def _linked_variant(record: RawEvidenceRecord, confidence: str) -> LinkedVariant:
    return LinkedVariant(
        source_id=record.source_id,
        title=record.title,
        url=record.url,
        variant_type=record.evidence_level or "variant",
        canonical_match_confidence=confidence,
        doi=record.doi,
        arxiv_id=record.arxiv_id,
        first_author=record.first_author,
        year=record.year,
    )


def _build_academic_slices(records: list[RawEvidenceRecord]) -> tuple[EvidenceSlice, ...]:
    slices: list[EvidenceSlice] = []
    seen_text: set[str] = set()
    for record in sorted(records, key=_academic_priority, reverse=True):
        snippet = record.snippet.strip()
        if not snippet or snippet in seen_text:
            continue
        seen_text.add(snippet)
        slices.append(
            EvidenceSlice(
                text=snippet,
                source_record_id=record.source_id,
                source_span="snippet",
                score=float(len(slices) == 0) + 0.5,
                token_estimate=record.token_estimate,
            )
        )
        if len(slices) == 2:
            break
    return tuple(slices)


def _group_confidence(aliases: set[tuple[str, ...]]) -> str:
    if any(alias[0] in {"doi", "arxiv"} for alias in aliases):
        return "strong_id"
    return "heuristic"


def _group_key_type(aliases: set[tuple[str, ...]]) -> str:
    if any(alias[0] == "doi" for alias in aliases):
        return "doi"
    if any(alias[0] == "arxiv" for alias in aliases):
        return "arxiv"
    if any(alias[0] == "heuristic" for alias in aliases):
        return "heuristic"
    return "source"


def _strong_aliases(record: RawEvidenceRecord) -> set[tuple[str, ...]]:
    return {
        alias
        for alias in _academic_aliases(record)
        if alias[0] in {"doi", "arxiv"}
    }


def _match_confidence(canonical_source: RawEvidenceRecord, record: RawEvidenceRecord) -> str:
    if _strong_aliases(canonical_source) & _strong_aliases(record):
        return "strong_id"
    return "heuristic"


def _canonical_group_confidence(
    canonical_source: RawEvidenceRecord,
    records: list[RawEvidenceRecord],
) -> str:
    other_records = [
        record
        for record in records
        if record.source_id != canonical_source.source_id or record.url != canonical_source.url
    ]
    if not other_records:
        return "strong_id" if _strong_aliases(canonical_source) else "heuristic"
    if all(_match_confidence(canonical_source, record) == "strong_id" for record in other_records):
        return "strong_id"
    return "heuristic"


def _stable_identifier(
    canonical_source: RawEvidenceRecord,
    aliases: set[tuple[str, ...]],
    key_type: str,
) -> str:
    if key_type == "doi":
        return next(alias[1] for alias in sorted(aliases) if alias[0] == "doi")
    if key_type == "arxiv":
        return next(alias[1] for alias in sorted(aliases) if alias[0] == "arxiv")
    if key_type == "heuristic":
        heuristic_alias = next(alias for alias in sorted(aliases) if alias[0] == "heuristic")
        return "-".join(heuristic_alias[1:])
    source_key = f"{canonical_source.source_id}:{canonical_source.url}".encode("utf-8")
    return hashlib.sha1(source_key).hexdigest()[:12]


def _merge_academic_group(records: list[RawEvidenceRecord], aliases: set[tuple[str, ...]]) -> CanonicalEvidence:
    prioritized_records = sorted(records, key=_academic_priority, reverse=True)
    canonical_source = prioritized_records[0]
    confidence = _canonical_group_confidence(canonical_source, prioritized_records)
    key_type = _group_key_type(aliases)
    stable_identifier = _stable_identifier(canonical_source, aliases, key_type)
    linked_variants = tuple(
        _linked_variant(record, _match_confidence(canonical_source, record))
        for record in prioritized_records
        if record.source_id != canonical_source.source_id or record.url != canonical_source.url
    )

    return CanonicalEvidence(
        evidence_id=f"academic:{key_type}:{stable_identifier}",
        domain="academic",
        canonical_title=canonical_source.title,
        canonical_url=canonical_source.url,
        raw_records=tuple(records),
        retained_slices=_build_academic_slices(records),
        linked_variants=linked_variants,
        authority=None,
        jurisdiction=None,
        jurisdiction_status=None,
        publication_date=None,
        effective_date=None,
        version=None,
        version_status=None,
        evidence_level=canonical_source.evidence_level,
        canonical_match_confidence=confidence,
        doi=canonical_source.doi or next((record.doi for record in prioritized_records if record.doi), None),
        arxiv_id=canonical_source.arxiv_id or next((record.arxiv_id for record in prioritized_records if record.arxiv_id), None),
        first_author=canonical_source.first_author,
        year=canonical_source.year,
        route_role="primary" if any(record.route_role == "primary" for record in records) else "supplemental",
        token_estimate=0,
    )


def canonicalize_academic_records(records: list[RawEvidenceRecord]) -> list[CanonicalEvidence]:
    """Collapse academic raw records into canonical evidence with linked variants."""

    grouped_records: list[_AcademicGroup] = []
    for record in records:
        aliases = _academic_aliases(record)
        matching_groups = [group for group in grouped_records if group.aliases & aliases]
        if not matching_groups:
            grouped_records.append(_AcademicGroup(records=[record], aliases=set(aliases)))
            continue

        primary_group = matching_groups[0]
        primary_group.records.append(record)
        primary_group.aliases.update(aliases)
        for group in matching_groups[1:]:
            primary_group.records.extend(group.records)
            primary_group.aliases.update(group.aliases)
            grouped_records.remove(group)

    canonical_records = [
        _merge_academic_group(group.records, group.aliases)
        for group in grouped_records
    ]
    return sorted(canonical_records, key=lambda item: item.evidence_id)
