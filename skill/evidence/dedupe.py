"""Domain-aware duplicate collapse for canonical evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from urllib.parse import urlparse

from skill.evidence.academic import canonicalize_academic_records
from skill.evidence.models import CanonicalEvidence, EvidenceSlice, RawEvidenceRecord
from skill.evidence.policy import canonicalize_policy_records

_TEXT_TOKEN_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class _IndustryGroup:
    host: str
    records: list[RawEvidenceRecord]


def _normalize_text(value: str) -> str:
    normalized = _TEXT_TOKEN_RE.sub(" ", value.lower())
    return " ".join(normalized.split())


def _domain_for_record(record: RawEvidenceRecord) -> str:
    if record.source_id.startswith("policy_") or record.authority and (
        record.publication_date or record.effective_date or record.version_status
    ):
        return "policy"
    if record.source_id.startswith("academic_") or any(
        [record.doi, record.arxiv_id, record.first_author, record.year, record.evidence_level]
    ):
        return "academic"
    return "industry"


def _same_domain(left: RawEvidenceRecord, right: RawEvidenceRecord) -> bool:
    return (urlparse(left.url).hostname or "") == (urlparse(right.url).hostname or "")


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=_normalize_text(left), b=_normalize_text(right)).ratio()


def _should_merge_industry(left: RawEvidenceRecord, right: RawEvidenceRecord) -> bool:
    if not _same_domain(left, right):
        return False

    title_similarity = _similarity(left.title, right.title)
    snippet_similarity = _similarity(left.snippet, right.snippet)
    # Conservative same-domain merge: require both high title and snippet similarity.
    return title_similarity >= 0.88 and snippet_similarity >= 0.72


def _merge_scalar(records: list[RawEvidenceRecord], field_name: str) -> object | None:
    for record in records:
        value = getattr(record, field_name)
        if value not in (None, ""):
            return value
    return None


def _build_industry_slices(records: list[RawEvidenceRecord]) -> tuple[EvidenceSlice, ...]:
    slices: list[EvidenceSlice] = []
    seen_text: set[str] = set()
    for record in records:
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


def _canonical_industry_title(records: list[RawEvidenceRecord]) -> str:
    return min(records, key=lambda record: (_normalize_text(record.title), len(record.title))).title


def _build_industry_canonical(group: _IndustryGroup) -> CanonicalEvidence:
    first_seen = group.records[0]
    canonical_title = _canonical_industry_title(group.records)
    host = group.host or "unknown-host"
    title_key = _normalize_text(canonical_title).replace(" ", "-")

    # Preserve raw_hits provenance in CanonicalEvidence.raw_records.
    return CanonicalEvidence(
        evidence_id=f"industry:{host}:{title_key}",
        domain="industry",
        canonical_title=canonical_title,
        canonical_url=first_seen.url,
        raw_records=tuple(group.records),
        retained_slices=_build_industry_slices(group.records),
        linked_variants=(),
        authority=_merge_scalar(group.records, "authority"),
        jurisdiction=_merge_scalar(group.records, "jurisdiction"),
        jurisdiction_status=_merge_scalar(group.records, "jurisdiction_status"),
        publication_date=_merge_scalar(group.records, "publication_date"),
        effective_date=_merge_scalar(group.records, "effective_date"),
        version=_merge_scalar(group.records, "version"),
        version_status=_merge_scalar(group.records, "version_status"),
        evidence_level=_merge_scalar(group.records, "evidence_level"),
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=_merge_scalar(group.records, "year"),
        route_role="primary" if any(record.route_role == "primary" for record in group.records) else "supplemental",
        token_estimate=0,
    )


def _collapse_industry_records(records: list[RawEvidenceRecord]) -> list[CanonicalEvidence]:
    groups: list[_IndustryGroup] = []
    for record in records:
        host = urlparse(record.url).hostname or ""
        for group in groups:
            if _should_merge_industry(record, group.records[0]):
                group.records.append(record)
                break
        else:
            groups.append(_IndustryGroup(host=host, records=[record]))

    canonical_records = [_build_industry_canonical(group) for group in groups]
    return sorted(canonical_records, key=lambda item: item.evidence_id)


def collapse_evidence_records(records: list[RawEvidenceRecord]) -> list[CanonicalEvidence]:
    """Collapse raw evidence into deterministic canonical records by domain."""

    policy_records: list[RawEvidenceRecord] = []
    academic_records: list[RawEvidenceRecord] = []
    industry_records: list[RawEvidenceRecord] = []

    for record in records:
        domain = _domain_for_record(record)
        if domain == "policy":
            policy_records.append(record)
        elif domain == "academic":
            academic_records.append(record)
        else:
            industry_records.append(record)

    canonical_records = [
        *canonicalize_policy_records(policy_records),
        *canonicalize_academic_records(academic_records),
        *_collapse_industry_records(industry_records),
    ]
    # Deterministic output: sort by canonical key while each group keeps first-seen raw record order.
    return sorted(canonical_records, key=lambda item: item.evidence_id)
