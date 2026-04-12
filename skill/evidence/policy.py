"""Policy-specific evidence canonicalization helpers."""

from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlparse

from skill.evidence.models import CanonicalEvidence, EvidenceSlice, RawEvidenceRecord

_POLICY_TITLE_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_POLICY_MIRROR_RE = re.compile(r"\bmirror\b", re.IGNORECASE)


def _normalize_policy_title(title: str) -> str:
    title = _POLICY_MIRROR_RE.sub("", title)
    title = _POLICY_TITLE_TOKEN_RE.sub(" ", title.lower())
    return " ".join(title.split())


def _slugify(value: str) -> str:
    return _normalize_policy_title(value).replace(" ", "-")


def _record_identity_matches(left: RawEvidenceRecord, right: RawEvidenceRecord) -> bool:
    if (left.authority or "").strip().lower() != (right.authority or "").strip().lower():
        return False
    if _normalize_policy_title(left.title) != _normalize_policy_title(right.title):
        return False

    shared_identity_values = (
        ("version", left.version, right.version),
        ("publication_date", left.publication_date, right.publication_date),
        ("effective_date", left.effective_date, right.effective_date),
    )
    return any(left_value and left_value == right_value for _, left_value, right_value in shared_identity_values)


def _policy_priority(record: RawEvidenceRecord) -> tuple[int, int, int, int, int]:
    normalized_title = _normalize_policy_title(record.title)
    return (
        1 if record.version else 0,
        1 if record.effective_date else 0,
        1 if record.jurisdiction else 0,
        1 if "mirror" not in record.title.lower() else 0,
        -len(normalized_title),
    )


def _infer_jurisdiction(records: list[RawEvidenceRecord]) -> tuple[str | None, str]:
    for record in records:
        if record.jurisdiction:
            return record.jurisdiction, "observed"

    for record in records:
        hostname = urlparse(record.url).hostname or ""
        if hostname.endswith(".gov.cn") or hostname.endswith(".gov"):
            return "CN", "jurisdiction_inferred"

    return None, "jurisdiction_unknown"


def _build_policy_slices(records: list[RawEvidenceRecord]) -> tuple[EvidenceSlice, ...]:
    slices: list[EvidenceSlice] = []
    seen_text: set[str] = set()
    for record in sorted(records, key=_policy_priority, reverse=True):
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


def _merge_policy_group(records: list[RawEvidenceRecord]) -> CanonicalEvidence:
    prioritized_records = sorted(records, key=_policy_priority, reverse=True)
    canonical_source = prioritized_records[0]
    publication_date = next((record.publication_date for record in prioritized_records if record.publication_date), None)
    effective_date = next((record.effective_date for record in prioritized_records if record.effective_date), None)
    version = next((record.version for record in prioritized_records if record.version), None)
    jurisdiction, jurisdiction_status = _infer_jurisdiction(prioritized_records)

    canonical_title = canonical_source.title.replace(" Mirror", "").strip()
    evidence_id_suffix = version or publication_date or effective_date or canonical_source.source_id
    return CanonicalEvidence(
        evidence_id=(
            f"policy:{_slugify(canonical_source.authority or 'unknown')}:"
            f"{_slugify(canonical_title)}:{_slugify(evidence_id_suffix)}"
        ),
        domain="policy",
        canonical_title=canonical_title,
        canonical_url=canonical_source.url,
        raw_records=tuple(records),
        retained_slices=_build_policy_slices(records),
        linked_variants=(),
        authority=canonical_source.authority,
        jurisdiction=jurisdiction,
        jurisdiction_status=jurisdiction_status,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
        version_status="observed" if version else "version_missing",
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
        route_role="primary" if any(record.route_role == "primary" for record in records) else "supplemental",
        token_estimate=0,
    )


def canonicalize_policy_records(records: list[RawEvidenceRecord]) -> list[CanonicalEvidence]:
    """Collapse policy raw records into canonical evidence with explicit metadata status."""

    accepted_records = [
        replace(record, title=record.title.strip())
        for record in records
        if record.authority and (record.publication_date or record.effective_date)
    ]
    grouped_records: list[list[RawEvidenceRecord]] = []
    for record in accepted_records:
        for group in grouped_records:
            if _record_identity_matches(record, group[0]):
                group.append(record)
                break
        else:
            grouped_records.append([record])

    canonical_records = [_merge_policy_group(group) for group in grouped_records]
    return sorted(canonical_records, key=lambda item: item.evidence_id)
