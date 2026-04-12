"""Phase 3 policy evidence regressions."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from skill.retrieval.models import RetrievalHit
from skill.evidence.models import CanonicalEvidence, EvidenceSlice, RawEvidenceRecord
from skill.evidence.normalize import build_raw_record

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evidence_phase3_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_policy_raw_record(**overrides: object) -> RawEvidenceRecord:
    case = _load_cases()["policy_duplicates"][0]
    hit = RetrievalHit(
        source_id=case["source_id"],
        title=case["title"],
        url=case["url"],
        snippet=case["snippet"],
        credibility_tier=case["credibility_tier"],
    )
    record = build_raw_record(hit=hit, route_role=case["route_role"])
    defaults = {
        "authority": case["authority"],
        "publication_date": case["publication_date"],
        "effective_date": case["effective_date"],
        "version": case["version"],
        "version_status": case["version_status"],
        "jurisdiction": case["jurisdiction"],
        "jurisdiction_status": case["jurisdiction_status"],
    }
    return replace(record, **(defaults | overrides))


def _make_policy_slice(source_record_id: str) -> EvidenceSlice:
    return EvidenceSlice(
        text="Policy evidence slice.",
        source_record_id=source_record_id,
        source_span="snippet",
        score=1.0,
        token_estimate=3,
    )


def test_policy_minimum_entry_requires_authority_and_a_date() -> None:
    base_record = _make_policy_raw_record()

    with pytest.raises(ValueError, match="authority"):
        CanonicalEvidence(
            evidence_id="policy-missing-authority",
            domain="policy",
            canonical_title=base_record.title,
            canonical_url=base_record.url,
            raw_records=(replace(base_record, authority=None),),
            retained_slices=(_make_policy_slice(base_record.source_id),),
            linked_variants=(),
            authority=None,
            jurisdiction="CN",
            jurisdiction_status="observed",
            publication_date="2024-02-15",
            effective_date=None,
            version="2024-02",
            version_status="observed",
            evidence_level=None,
            canonical_match_confidence=None,
            doi=None,
            arxiv_id=None,
            first_author=None,
            year=None,
            route_role="primary",
            token_estimate=0,
        )

    with pytest.raises(ValueError, match="date"):
        CanonicalEvidence(
            evidence_id="policy-missing-dates",
            domain="policy",
            canonical_title=base_record.title,
            canonical_url=base_record.url,
            raw_records=(base_record,),
            retained_slices=(_make_policy_slice(base_record.source_id),),
            linked_variants=(),
            authority=base_record.authority,
            jurisdiction="CN",
            jurisdiction_status="observed",
            publication_date=None,
            effective_date=None,
            version="2024-02",
            version_status="observed",
            evidence_level=None,
            canonical_match_confidence=None,
            doi=None,
            arxiv_id=None,
            first_author=None,
            year=None,
            route_role="primary",
            token_estimate=0,
        )

    canonical = CanonicalEvidence(
        evidence_id="policy-complete",
        domain="policy",
        canonical_title=base_record.title,
        canonical_url=base_record.url,
        raw_records=(base_record,),
        retained_slices=(_make_policy_slice(base_record.source_id),),
        linked_variants=(),
        authority=base_record.authority,
        jurisdiction=None,
        jurisdiction_status="jurisdiction_unknown",
        publication_date=base_record.publication_date,
        effective_date=None,
        version=None,
        version_status="version_missing",
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
        route_role="primary",
        token_estimate=0,
    )

    assert canonical.authority == "Ministry of Ecology and Environment"
    assert canonical.publication_date == "2024-02-15"


def test_policy_requires_explicit_version_status_and_jurisdiction_status() -> None:
    base_record = _make_policy_raw_record()

    with pytest.raises(ValueError, match="version_status"):
        CanonicalEvidence(
            evidence_id="policy-status-missing",
            domain="policy",
            canonical_title=base_record.title,
            canonical_url=base_record.url,
            raw_records=(base_record,),
            retained_slices=(_make_policy_slice(base_record.source_id),),
            linked_variants=(),
            authority=base_record.authority,
            jurisdiction=None,
            jurisdiction_status="jurisdiction_unknown",
            publication_date=base_record.publication_date,
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

    with pytest.raises(ValueError, match="jurisdiction_status"):
        CanonicalEvidence(
            evidence_id="policy-jurisdiction-status-missing",
            domain="policy",
            canonical_title=base_record.title,
            canonical_url=base_record.url,
            raw_records=(base_record,),
            retained_slices=(_make_policy_slice(base_record.source_id),),
            linked_variants=(),
            authority=base_record.authority,
            jurisdiction=None,
            jurisdiction_status=None,
            publication_date=base_record.publication_date,
            effective_date=None,
            version=None,
            version_status="version_missing",
            evidence_level=None,
            canonical_match_confidence=None,
            doi=None,
            arxiv_id=None,
            first_author=None,
            year=None,
            route_role="primary",
            token_estimate=0,
        )

    inferred = CanonicalEvidence(
        evidence_id="policy-inferred-jurisdiction",
        domain="policy",
        canonical_title=base_record.title,
        canonical_url=base_record.url,
        raw_records=(base_record,),
        retained_slices=(_make_policy_slice(base_record.source_id),),
        linked_variants=(),
        authority=base_record.authority,
        jurisdiction="China",
        jurisdiction_status="jurisdiction_inferred",
        publication_date=base_record.publication_date,
        effective_date=None,
        version=None,
        version_status="version_missing",
        evidence_level=None,
        canonical_match_confidence=None,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
        route_role="primary",
        token_estimate=0,
    )

    assert inferred.version_status == "version_missing"
    assert inferred.jurisdiction_status == "jurisdiction_inferred"


def test_build_raw_record_keeps_policy_metadata_unknown_until_observed() -> None:
    case = _load_cases()["policy_duplicates"][1]
    hit = RetrievalHit(
        source_id=case["source_id"],
        title=case["title"],
        url=case["url"],
        snippet=case["snippet"],
        credibility_tier=case["credibility_tier"],
    )

    record = build_raw_record(hit=hit, route_role=case["route_role"])

    assert record.authority is None
    assert record.publication_date is None
    assert record.effective_date is None
    assert record.version is None
    assert record.version_status == "version_missing"
    assert record.jurisdiction is None
    assert record.jurisdiction_status == "jurisdiction_unknown"


def test_canonicalize_policy_records_merges_version_aware_policy_duplicates() -> None:
    from skill.evidence.policy import canonicalize_policy_records

    canonical_records = canonicalize_policy_records(
        [
            _make_policy_raw_record(),
            _make_policy_raw_record(
                authority="Ministry of Ecology and Environment",
                publication_date="2024-02-15",
                effective_date=None,
                version=None,
                version_status="version_missing",
                jurisdiction=None,
                jurisdiction_status="jurisdiction_unknown",
            ),
        ]
    )

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.canonical_title == "National Air Quality Rule 2024"
    assert canonical.canonical_url == "https://www.mee.gov.cn/policy/air-quality-2024"
    assert canonical.publication_date == "2024-02-15"
    assert canonical.effective_date == "2024-03-01"
    assert canonical.version == "2024-02"
    assert canonical.version_status == "observed"
    assert canonical.jurisdiction == "CN"
    assert canonical.jurisdiction_status == "observed"
    assert len(canonical.raw_records) == 2


def test_canonicalize_policy_records_rejects_entries_missing_minimum_metadata() -> None:
    from skill.evidence.policy import canonicalize_policy_records

    canonical_records = canonicalize_policy_records(
        [
            _make_policy_raw_record(
                authority=None,
                publication_date=None,
                effective_date=None,
            ),
            _make_policy_raw_record(
                title="Standalone Notice Without Version",
                url="https://www.gov.cn/notice/standalone",
                authority="State Council",
                publication_date="2024-04-12",
                effective_date=None,
                version=None,
                version_status="version_missing",
                jurisdiction=None,
                jurisdiction_status="jurisdiction_unknown",
            ),
        ]
    )

    assert len(canonical_records) == 1
    assert canonical_records[0].authority == "State Council"
    assert canonical_records[0].version_status == "version_missing"
    assert canonical_records[0].jurisdiction_status in {
        "jurisdiction_inferred",
        "jurisdiction_unknown",
    }


def test_canonicalize_policy_records_infers_us_for_dot_gov_hosts() -> None:
    from skill.evidence.policy import canonicalize_policy_records

    canonical_records = canonicalize_policy_records(
        [
            _make_policy_raw_record(
                authority="Environmental Protection Agency",
                title="EPA Rule Bulletin",
                url="https://www.epa.gov/rule/bulletin",
                publication_date="2024-04-12",
                effective_date=None,
                version=None,
                version_status="version_missing",
                jurisdiction=None,
                jurisdiction_status="jurisdiction_unknown",
            )
        ]
    )

    assert len(canonical_records) == 1
    assert canonical_records[0].jurisdiction == "US"
    assert canonical_records[0].jurisdiction_status == "jurisdiction_inferred"
