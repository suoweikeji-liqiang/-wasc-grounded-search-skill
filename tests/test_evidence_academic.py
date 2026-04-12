"""Phase 3 academic evidence regressions."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from skill.retrieval.models import RetrievalHit
from skill.evidence.models import CanonicalEvidence, EvidenceSlice, LinkedVariant, RawEvidenceRecord
from skill.evidence.normalize import build_raw_record

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evidence_phase3_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_academic_raw_record(case_index: int, **overrides: object) -> RawEvidenceRecord:
    case = _load_cases()["academic_variants"][case_index]
    hit = RetrievalHit(
        source_id=case["source_id"],
        title=case["title"],
        url=case["url"],
        snippet=case["snippet"],
        credibility_tier=case["credibility_tier"],
    )
    record = build_raw_record(hit=hit, route_role=case["route_role"])
    defaults = {
        "doi": case["doi"],
        "arxiv_id": case["arxiv_id"],
        "first_author": case["first_author"],
        "year": case["year"],
        "evidence_level": case["evidence_level"],
    }
    return replace(record, **(defaults | overrides))


def _make_slice(source_record_id: str) -> EvidenceSlice:
    return EvidenceSlice(
        text="Academic evidence slice.",
        source_record_id=source_record_id,
        source_span="snippet",
        score=0.95,
        token_estimate=3,
    )


def test_published_variant_can_anchor_canonical_academic_record() -> None:
    published = _make_academic_raw_record(0)
    preprint = _make_academic_raw_record(1)
    linked_variant = LinkedVariant(
        source_id=preprint.source_id,
        title=preprint.title,
        url=preprint.url,
        variant_type="preprint",
        canonical_match_confidence="strong_id",
        doi=preprint.doi,
        arxiv_id=preprint.arxiv_id,
        first_author=preprint.first_author,
        year=preprint.year,
    )

    canonical = CanonicalEvidence(
        evidence_id="academic-published-first",
        domain="academic",
        canonical_title=published.title,
        canonical_url=published.url,
        raw_records=(published, preprint),
        retained_slices=(_make_slice(published.source_id),),
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
        doi=published.doi,
        arxiv_id=published.arxiv_id,
        first_author=published.first_author,
        year=published.year,
        route_role="primary",
        token_estimate=0,
    )

    assert canonical.canonical_url == "https://doi.org/10.5555/evidence.2025.10"
    assert canonical.evidence_level == "peer_reviewed"
    assert canonical.linked_variants[0].variant_type == "preprint"


def test_heuristic_academic_matches_require_explicit_confidence_marker() -> None:
    heuristic = _make_academic_raw_record(2)
    linked_variant = LinkedVariant(
        source_id="academic_arxiv",
        title="Grounded Search Evidence Packing (working paper)",
        url="https://arxiv.org/abs/2401.00001",
        variant_type="preprint",
        canonical_match_confidence="heuristic",
        doi=None,
        arxiv_id="2401.00001",
        first_author=heuristic.first_author,
        year=heuristic.year,
    )

    with pytest.raises(ValueError, match="canonical_match_confidence"):
        CanonicalEvidence(
            evidence_id="academic-heuristic-unmarked",
            domain="academic",
            canonical_title=heuristic.title,
            canonical_url=heuristic.url,
            raw_records=(heuristic,),
            retained_slices=(_make_slice(heuristic.source_id),),
            linked_variants=(linked_variant,),
            authority=None,
            jurisdiction=None,
            jurisdiction_status=None,
            publication_date=None,
            effective_date=None,
            version=None,
            version_status=None,
            evidence_level="metadata_only",
            canonical_match_confidence=None,
            doi=heuristic.doi,
            arxiv_id=heuristic.arxiv_id,
            first_author=heuristic.first_author,
            year=heuristic.year,
            route_role="supplemental",
            token_estimate=0,
        )

    canonical = CanonicalEvidence(
        evidence_id="academic-heuristic-marked",
        domain="academic",
        canonical_title=heuristic.title,
        canonical_url=heuristic.url,
        raw_records=(heuristic,),
        retained_slices=(_make_slice(heuristic.source_id),),
        linked_variants=(linked_variant,),
        authority=None,
        jurisdiction=None,
        jurisdiction_status=None,
        publication_date=None,
        effective_date=None,
        version=None,
        version_status=None,
        evidence_level="metadata_only",
        canonical_match_confidence="heuristic",
        doi=heuristic.doi,
        arxiv_id=heuristic.arxiv_id,
        first_author=heuristic.first_author,
        year=heuristic.year,
        route_role="supplemental",
        token_estimate=0,
    )

    assert canonical.canonical_match_confidence == "heuristic"
    assert canonical.linked_variants[0].canonical_match_confidence == "heuristic"


def test_canonicalize_academic_records_prefers_published_variant_and_links_preprint() -> None:
    from skill.evidence.academic import canonicalize_academic_records

    canonical_records = canonicalize_academic_records(
        [
            _make_academic_raw_record(1),
            _make_academic_raw_record(0),
        ]
    )

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.canonical_title == "Evidence Normalization for Retrieval-Augmented Systems"
    assert canonical.canonical_url == "https://doi.org/10.5555/evidence.2025.10"
    assert canonical.doi == "10.5555/evidence.2025.10"
    assert canonical.evidence_level == "peer_reviewed"
    assert canonical.canonical_match_confidence == "strong_id"
    assert len(canonical.linked_variants) == 1
    assert canonical.linked_variants[0].variant_type == "preprint"


def test_canonicalize_academic_records_marks_title_author_year_merges_as_heuristic() -> None:
    from skill.evidence.academic import canonicalize_academic_records

    heuristic = _make_academic_raw_record(2)
    working_paper = replace(
        heuristic,
        source_id="academic_open_repository",
        title="Grounded Search Evidence Packing Working Paper",
        url="https://example.org/working-paper",
        snippet="Working paper variant of the evidence packing research.",
        evidence_level="preprint",
        route_role="supplemental",
    )

    canonical_records = canonicalize_academic_records([heuristic, working_paper])

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.canonical_match_confidence == "heuristic"
    assert canonical.evidence_level == "preprint"
    assert len(canonical.linked_variants) == 1
    assert canonical.linked_variants[0].canonical_match_confidence == "heuristic"


def test_canonicalize_academic_records_keeps_mixed_confidence_merges_heuristic() -> None:
    from skill.evidence.academic import canonicalize_academic_records

    doi_backed = _make_academic_raw_record(0)
    metadata_only = replace(
        _make_academic_raw_record(2),
        title=doi_backed.title,
        first_author=doi_backed.first_author,
        year=doi_backed.year,
        doi=None,
        arxiv_id=None,
        evidence_level="metadata_only",
        source_id="academic_openalex",
        url="https://openalex.org/work/W123456789",
    )

    canonical_records = canonicalize_academic_records([doi_backed, metadata_only])

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.canonical_match_confidence == "heuristic"
    assert len(canonical.linked_variants) == 1
    assert canonical.linked_variants[0].source_id == "academic_openalex"
    assert canonical.linked_variants[0].canonical_match_confidence == "heuristic"


def test_canonicalize_academic_records_uses_unique_source_ids_without_scholarly_ids() -> None:
    from skill.evidence.academic import canonicalize_academic_records

    source_only_a = replace(
        _make_academic_raw_record(2),
        source_id="academic_catalog_a",
        title="Repeated Title",
        url="https://catalog-a.example/paper",
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
    )
    source_only_b = replace(
        _make_academic_raw_record(2),
        source_id="academic_catalog_b",
        title="Repeated Title",
        url="https://catalog-b.example/paper",
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
    )

    canonical_records = canonicalize_academic_records([source_only_a, source_only_b])

    assert len(canonical_records) == 2
    assert len({record.evidence_id for record in canonical_records}) == 2
