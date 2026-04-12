"""Runtime evidence normalization regressions using the real live-hit path."""

from __future__ import annotations

import asyncio

from skill.evidence.dedupe import collapse_evidence_records
from skill.evidence.normalize import build_raw_record, normalize_hit_candidates
from skill.retrieval.adapters.academic_arxiv import search as arxiv_search
from skill.retrieval.adapters.academic_semantic_scholar import search as semantic_search
from skill.retrieval.adapters.policy_official_registry import search as policy_search
from skill.retrieval.models import RetrievalHit


def test_live_policy_hits_survive_normalization_and_keep_explicit_missing_markers() -> None:
    live_policy_hits = asyncio.run(policy_search("official policy bulletin"))
    partial_policy_hit = RetrievalHit(
        source_id="policy_official_registry",
        title="Emergency Water Use Notice",
        url="https://www.mee.gov.cn/policy/water-use-notice",
        snippet="Official notice with authority and publication date but no version.",
        authority="Ministry of Ecology and Environment",
        publication_date="2026-01-10",
    )

    canonical_records = collapse_evidence_records(
        normalize_hit_candidates(
            [*live_policy_hits, partial_policy_hit],
            route_role_by_source={},
        )
    )

    policy_records = [record for record in canonical_records if record.domain == "policy"]

    assert policy_records
    assert any(
        record.authority and (record.publication_date or record.effective_date)
        for record in policy_records
    )
    assert any(record.version_status == "version_missing" for record in policy_records)
    assert any(
        record.jurisdiction_status in {"jurisdiction_inferred", "jurisdiction_unknown"}
        for record in policy_records
    )


def test_live_academic_hits_merge_published_and_preprint_variants() -> None:
    published_hit = next(
        hit
        for hit in asyncio.run(semantic_search("evidence normalization"))
        if hit.first_author == "Lin"
    )
    preprint_hit = next(
        hit
        for hit in asyncio.run(arxiv_search("evidence normalization"))
        if hit.first_author == "Lin"
    )

    canonical_records = collapse_evidence_records(
        normalize_hit_candidates(
            [published_hit, preprint_hit],
            route_role_by_source={"academic_arxiv": "supplemental"},
        )
    )

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.domain == "academic"
    assert canonical.evidence_level == "peer_reviewed"
    assert canonical.doi == published_hit.doi
    assert canonical.arxiv_id == preprint_hit.arxiv_id
    assert canonical.first_author == "Lin"
    assert canonical.year == 2025
    assert canonical.canonical_match_confidence == "heuristic"
    assert len(canonical.linked_variants) == 1
    assert canonical.linked_variants[0].variant_type == "preprint"
    assert canonical.linked_variants[0].canonical_match_confidence == "heuristic"


def test_build_raw_record_preserves_raw_hit_and_only_maps_observed_metadata() -> None:
    policy_hit = RetrievalHit(
        source_id="policy_official_registry",
        title="Circular on Water Monitoring",
        url="https://www.mee.gov.cn/policy/water-monitoring",
        snippet="Circular with observed authority and publication date only.",
        authority="Ministry of Ecology and Environment",
        publication_date="2026-02-02",
    )
    academic_hit = RetrievalHit(
        source_id="academic_arxiv",
        title="Runtime evidence normalization preprint",
        url="https://arxiv.org/abs/2605.00001",
        snippet="Preprint with arXiv identity but no DOI.",
        arxiv_id="2605.00001",
        first_author="Chen",
        year=2026,
        evidence_level="preprint",
    )

    policy_record = build_raw_record(policy_hit, route_role="primary")
    academic_record = build_raw_record(academic_hit, route_role="supplemental")

    assert policy_record.raw_hit is policy_hit
    assert policy_record.authority == "Ministry of Ecology and Environment"
    assert policy_record.publication_date == "2026-02-02"
    assert policy_record.effective_date is None
    assert policy_record.version is None
    assert policy_record.version_status == "version_missing"
    assert policy_record.jurisdiction is None
    assert policy_record.jurisdiction_status == "jurisdiction_unknown"
    assert policy_record.doi is None
    assert policy_record.canonical_match_confidence is None

    assert academic_record.raw_hit is academic_hit
    assert academic_record.arxiv_id == "2605.00001"
    assert academic_record.first_author == "Chen"
    assert academic_record.year == 2026
    assert academic_record.evidence_level == "preprint"
    assert academic_record.doi is None
    assert academic_record.canonical_match_confidence is None
