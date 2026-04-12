"""Helpers for turning retrieval hits into evidence-layer raw records."""

from __future__ import annotations

import re
from collections.abc import Mapping

from skill.evidence.models import RawEvidenceRecord
from skill.retrieval.models import RetrievalHit

_TOKEN_PATTERN = re.compile(r"\S+")


def _estimate_token_count(text: str) -> int:
    return len(_TOKEN_PATTERN.findall(text))


def _policy_jurisdiction_status(hit: RetrievalHit) -> str | None:
    if not hit.source_id.startswith("policy_"):
        return None
    return "observed" if hit.jurisdiction else "jurisdiction_unknown"


def _policy_version_status(hit: RetrievalHit) -> str | None:
    if not hit.source_id.startswith("policy_"):
        return None
    return "observed" if hit.version else "version_missing"


def build_raw_record(hit: RetrievalHit, route_role: str) -> RawEvidenceRecord:
    return RawEvidenceRecord(
        source_id=hit.source_id,
        title=hit.title,
        url=hit.url,
        snippet=hit.snippet,
        credibility_tier=hit.credibility_tier,
        route_role=route_role,
        token_estimate=_estimate_token_count(hit.snippet),
        raw_hit=hit,
        authority=hit.authority,
        jurisdiction=hit.jurisdiction,
        jurisdiction_status=_policy_jurisdiction_status(hit),
        publication_date=hit.publication_date,
        effective_date=hit.effective_date,
        version=hit.version,
        version_status=_policy_version_status(hit),
        evidence_level=hit.evidence_level,
        canonical_match_confidence=None,
        doi=hit.doi,
        arxiv_id=hit.arxiv_id,
        first_author=hit.first_author,
        year=hit.year,
    )


def normalize_hit_candidates(
    hits: list[RetrievalHit],
    route_role_by_source: Mapping[str, str],
) -> list[RawEvidenceRecord]:
    records: list[RawEvidenceRecord] = []
    for hit in hits:
        route_role = route_role_by_source.get(hit.source_id, "primary")
        records.append(build_raw_record(hit=hit, route_role=route_role))
    return records
