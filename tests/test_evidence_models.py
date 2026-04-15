"""Phase 3 evidence contract regressions."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from skill.retrieval.models import RetrievalHit
from skill.evidence.models import (
    CanonicalEvidence,
    EvidencePack,
    EvidenceSlice,
    LinkedVariant,
    RawEvidenceRecord,
)
from skill.evidence.normalize import build_raw_record, normalize_hit_candidates

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evidence_phase3_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_raw_record(**overrides: object) -> RawEvidenceRecord:
    hit = RetrievalHit(
        source_id="industry_ddgs",
        title="Evidence contract background",
        url="https://example.com/evidence-contract",
        snippet="Industry evidence contract snippet for normalization.",
        credibility_tier="trusted_news",
    )
    record = build_raw_record(hit=hit, route_role="primary")
    return replace(record, **overrides)


def test_phase3_fixture_covers_policy_academic_and_mixed_routes() -> None:
    cases = _load_cases()

    assert cases["policy_duplicates"][1]["version_status"] == "version_missing"
    assert cases["policy_duplicates"][1]["jurisdiction_status"] == "jurisdiction_unknown"
    assert cases["academic_variants"][2]["canonical_match_confidence"] == "heuristic"
    assert {
        candidate["route_role"] for candidate in cases["mixed_route_candidates"]
    } == {"primary", "supplemental"}


def test_build_raw_record_preserves_retrieval_hit_provenance() -> None:
    hit = RetrievalHit(
        source_id="policy_official_registry",
        title="Policy source",
        url="https://www.gov.cn/policy",
        snippet="Primary route evidence snippet",
        credibility_tier="official_government",
    )

    record = build_raw_record(hit=hit, route_role="primary")

    assert record == RawEvidenceRecord(
        source_id=hit.source_id,
        title=hit.title,
        url=hit.url,
        snippet=hit.snippet,
        credibility_tier=hit.credibility_tier,
        route_role="primary",
        token_estimate=4,
        raw_hit=hit,
        authority=None,
        jurisdiction=None,
        jurisdiction_status="jurisdiction_unknown",
        publication_date=None,
        effective_date=None,
        version=None,
        version_status="version_missing",
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
    )


def test_build_raw_record_preserves_variant_provenance() -> None:
    hit = RetrievalHit(
        source_id="policy_official_registry",
        title="EU DORA ICT incident reporting timeline",
        url="https://eur-lex.europa.eu/dora-reporting",
        snippet="DORA defines ICT incident reporting timeline and follow-up report duties.",
        credibility_tier="official_government",
        target_route="policy",
        variant_reason_codes=("original", "cross_domain_fragment_focus"),
        variant_queries=(
            "EU DORA ICT incident reporting timeline and SaaS vendor incident update notice",
            "EU DORA ICT incident reporting timeline",
        ),
    )

    record = build_raw_record(hit=hit, route_role="primary")

    assert record.target_route == "policy"
    assert record.variant_reason_codes == (
        "original",
        "cross_domain_fragment_focus",
    )
    assert record.variant_queries == (
        "EU DORA ICT incident reporting timeline and SaaS vendor incident update notice",
        "EU DORA ICT incident reporting timeline",
    )


def test_normalize_hit_candidates_applies_route_role_by_source() -> None:
    policy_hit = RetrievalHit(
        source_id="policy_official_registry",
        title="Policy result",
        url="https://www.gov.cn/policy",
        snippet="Primary route policy evidence",
    )
    academic_hit = RetrievalHit(
        source_id="academic_semantic_scholar",
        title="Academic result",
        url="https://www.semanticscholar.org/paper/123",
        snippet="Supporting academic evidence",
    )

    records = normalize_hit_candidates(
        hits=[policy_hit, academic_hit],
        route_role_by_source={"academic_semantic_scholar": "supplemental"},
    )

    assert [record.route_role for record in records] == ["primary", "supplemental"]
    assert [record.source_id for record in records] == [
        "policy_official_registry",
        "academic_semantic_scholar",
    ]


def test_canonical_evidence_is_frozen_and_limits_retained_slices() -> None:
    raw_record = _make_raw_record()
    slice_one = EvidenceSlice(
        text="Alpha evidence.",
        source_record_id=raw_record.source_id,
        source_span="snippet",
        score=0.9,
        token_estimate=2,
    )
    slice_two = EvidenceSlice(
        text="Beta evidence.",
        source_record_id=raw_record.source_id,
        source_span="snippet",
        score=0.7,
        token_estimate=2,
    )

    canonical = CanonicalEvidence(
        evidence_id="industry-example",
        domain="industry",
        canonical_title=raw_record.title,
        canonical_url=raw_record.url,
        raw_records=(raw_record,),
        retained_slices=(slice_one, slice_two),
        linked_variants=(),
        authority=None,
        jurisdiction=None,
        jurisdiction_status=None,
        publication_date=None,
        effective_date=None,
        version=None,
        version_status=None,
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
        route_role="primary",
        token_estimate=0,
    )

    with pytest.raises(FrozenInstanceError):
        canonical.canonical_title = "Changed title"  # type: ignore[misc]

    with pytest.raises(ValueError, match="retained_slices"):
        CanonicalEvidence(
            evidence_id="industry-too-many-slices",
            domain="industry",
            canonical_title=raw_record.title,
            canonical_url=raw_record.url,
            raw_records=(raw_record,),
            retained_slices=(
                slice_one,
                slice_two,
                EvidenceSlice(
                    text="Gamma evidence.",
                    source_record_id=raw_record.source_id,
                    source_span="snippet",
                    score=0.4,
                    token_estimate=2,
                ),
            ),
            linked_variants=(),
            authority=None,
            jurisdiction=None,
            jurisdiction_status=None,
            publication_date=None,
            effective_date=None,
            version=None,
            version_status=None,
            evidence_level=None,
            canonical_match_confidence=None,
            doi=None,
            arxiv_id=None,
            first_author=None,
            year=None,
            route_role="primary",
            token_estimate=0,
        )


def test_linked_variants_and_evidence_pack_keep_raw_and_canonical_records() -> None:
    raw_record = _make_raw_record()
    linked_variant = LinkedVariant(
        source_id="academic_arxiv",
        title="Evidence contract preprint",
        url="https://arxiv.org/abs/2501.01234",
        variant_type="preprint",
        canonical_match_confidence="strong_id",
        doi=None,
        arxiv_id="2501.01234",
        first_author="Chen",
        year=2025,
    )
    canonical = CanonicalEvidence(
        evidence_id="academic-evidence-contract",
        domain="academic",
        canonical_title="Evidence contract published paper",
        canonical_url="https://doi.org/10.5555/evidence.2025.10",
        raw_records=(raw_record,),
        retained_slices=(
            EvidenceSlice(
                text="Published evidence slice.",
                source_record_id=raw_record.source_id,
                source_span="snippet",
                score=1.0,
                token_estimate=3,
            ),
        ),
        linked_variants=(linked_variant,),
        authority=None,
        jurisdiction=None,
        jurisdiction_status=None,
        publication_date=None,
        effective_date=None,
        version=None,
        version_status=None,
        evidence_level="peer_reviewed",
        canonical_match_confidence="strong_id",
        doi="10.5555/evidence.2025.10",
        arxiv_id="2501.01234",
        first_author="Chen",
        year=2025,
        route_role="primary",
        token_estimate=0,
    )
    pack = EvidencePack(
        raw_records=(raw_record,),
        canonical_evidence=(canonical,),
        clipped=False,
        pruned=False,
        total_token_estimate=0,
    )

    assert canonical.linked_variants[0].variant_type == "preprint"
    assert canonical.raw_records[0] is raw_record
    assert pack.raw_records == (raw_record,)
    assert pack.canonical_evidence == (canonical,)
