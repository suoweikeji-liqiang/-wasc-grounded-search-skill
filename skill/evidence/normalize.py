"""Helpers for turning retrieval hits into evidence-layer raw records."""

from __future__ import annotations

import re
from collections.abc import Mapping

from skill.evidence.models import RawEvidenceRecord
from skill.retrieval.models import RetrievalHit

_TOKEN_PATTERN = re.compile(r"\S+")


def _estimate_token_count(text: str) -> int:
    return len(_TOKEN_PATTERN.findall(text))


def build_raw_record(hit: RetrievalHit, route_role: str) -> RawEvidenceRecord:
    jurisdiction_status: str | None = None
    version_status: str | None = None
    if hit.source_id.startswith("policy_"):
        jurisdiction_status = "jurisdiction_unknown"
        version_status = "version_missing"

    return RawEvidenceRecord(
        source_id=hit.source_id,
        title=hit.title,
        url=hit.url,
        snippet=hit.snippet,
        credibility_tier=hit.credibility_tier,
        route_role=route_role,
        token_estimate=_estimate_token_count(hit.snippet),
        raw_hit=hit,
        authority=None,
        jurisdiction=None,
        jurisdiction_status=jurisdiction_status,
        publication_date=None,
        effective_date=None,
        version=None,
        version_status=version_status,
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
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
