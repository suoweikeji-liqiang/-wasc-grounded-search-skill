"""Phase 3 duplicate-collapse regressions."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from skill.evidence.models import RawEvidenceRecord
from skill.evidence.normalize import build_raw_record
from skill.retrieval.models import RetrievalHit

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evidence_phase3_cases.json"


def _load_cases() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _record_from_payload(payload: dict[str, object], **overrides: object) -> RawEvidenceRecord:
    hit = RetrievalHit(
        source_id=str(payload["source_id"]),
        title=str(payload["title"]),
        url=str(payload["url"]),
        snippet=str(payload["snippet"]),
        credibility_tier=payload.get("credibility_tier"),
    )
    record = build_raw_record(hit=hit, route_role=str(payload["route_role"]))
    metadata = {
        "authority": payload.get("authority"),
        "jurisdiction": payload.get("jurisdiction"),
        "jurisdiction_status": payload.get("jurisdiction_status"),
        "publication_date": payload.get("publication_date"),
        "effective_date": payload.get("effective_date"),
        "version": payload.get("version"),
        "version_status": payload.get("version_status"),
        "evidence_level": payload.get("evidence_level"),
        "canonical_match_confidence": payload.get("canonical_match_confidence"),
        "doi": payload.get("doi"),
        "arxiv_id": payload.get("arxiv_id"),
        "first_author": payload.get("first_author"),
        "year": payload.get("year"),
    }
    return replace(record, **(metadata | overrides))


def test_collapse_evidence_records_routes_domain_canonicalizers_and_preserves_first_seen_order() -> None:
    from skill.evidence.dedupe import collapse_evidence_records

    cases = _load_cases()
    policy_records = [
        _record_from_payload(cases["policy_duplicates"][1]),
        _record_from_payload(cases["policy_duplicates"][0]),
    ]
    academic_records = [
        _record_from_payload(cases["academic_variants"][1]),
        _record_from_payload(cases["academic_variants"][0]),
    ]

    canonical_records = collapse_evidence_records(policy_records + academic_records)

    assert [record.domain for record in canonical_records] == ["academic", "policy"]
    assert canonical_records[0].linked_variants[0].variant_type == "preprint"
    assert canonical_records[1].raw_records[0].source_id == "policy_official_web_allowlist_fallback"


def test_collapse_evidence_records_merges_same_domain_industry_duplicates_and_keeps_raw_hits() -> None:
    from skill.evidence.dedupe import collapse_evidence_records

    first = _record_from_payload(
        {
            "source_id": "industry_company_news",
            "title": "Acme opens battery plant in Hunan",
            "url": "https://acme.com/news/battery-plant-hunan",
            "snippet": "Acme opened a battery plant in Hunan to expand EV production.",
            "credibility_tier": "company_official",
            "route_role": "primary",
        },
        publication_date="2024-04-01",
        authority=None,
    )
    duplicate = _record_from_payload(
        {
            "source_id": "industry_company_blog",
            "title": "Acme opens new battery plant in Hunan",
            "url": "https://acme.com/blog/hunan-battery-plant",
            "snippet": "Acme opened a new battery plant in Hunan to expand EV production capacity.",
            "credibility_tier": "company_official",
            "route_role": "primary",
        },
        publication_date=None,
        authority="Acme Corp",
    )

    canonical_records = collapse_evidence_records([duplicate, first])

    assert len(canonical_records) == 1
    canonical = canonical_records[0]
    assert canonical.domain == "industry"
    assert canonical.authority == "Acme Corp"
    assert canonical.publication_date == "2024-04-01"
    assert len(canonical.raw_records) == 2
    assert canonical.raw_records[0].source_id == "industry_company_blog"


def test_collapse_evidence_records_rejects_event_level_over_merging() -> None:
    from skill.evidence.dedupe import collapse_evidence_records

    company_post = _record_from_payload(
        {
            "source_id": "industry_company_post",
            "title": "Acme opens battery plant in Hunan",
            "url": "https://acme.com/news/battery-plant-hunan",
            "snippet": "Acme opened a battery plant in Hunan to expand EV production.",
            "credibility_tier": "company_official",
            "route_role": "primary",
        },
        authority="Acme Corp",
    )
    supplier_post = _record_from_payload(
        {
            "source_id": "industry_supplier_post",
            "title": "Supplier ships equipment for Hunan battery plant",
            "url": "https://supplier.example.com/news/hunan-battery-plant",
            "snippet": "Supplier delivered equipment for the Hunan battery plant opening.",
            "credibility_tier": "industry_news",
            "route_role": "primary",
        },
        authority="Supplier Ltd",
    )

    canonical_records = collapse_evidence_records([company_post, supplier_post])

    assert len(canonical_records) == 2
    assert {record.canonical_url for record in canonical_records} == {
        "https://acme.com/news/battery-plant-hunan",
        "https://supplier.example.com/news/hunan-battery-plant",
    }


def test_collapse_evidence_records_keeps_unique_ids_for_same_host_same_title_articles() -> None:
    from skill.evidence.dedupe import collapse_evidence_records

    first_story = _record_from_payload(
        {
            "source_id": "industry_company_news",
            "title": "Quarterly Update",
            "url": "https://acme.com/news/q1-update",
            "snippet": "Acme reported battery output growth in the first quarter.",
            "credibility_tier": "company_official",
            "route_role": "primary",
        }
    )
    second_story = _record_from_payload(
        {
            "source_id": "industry_company_news_2",
            "title": "Quarterly Update",
            "url": "https://acme.com/news/q2-update",
            "snippet": "Leadership announced a board transition and a new audit committee chair.",
            "credibility_tier": "company_official",
            "route_role": "primary",
        }
    )

    canonical_records = collapse_evidence_records([first_story, second_story])

    assert len(canonical_records) == 2
    assert len({record.evidence_id for record in canonical_records}) == 2
