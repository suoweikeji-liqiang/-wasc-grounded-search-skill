"""Phase 3 evidence scoring and budget packing regressions."""

from __future__ import annotations

from dataclasses import replace

from skill.evidence.models import CanonicalEvidence, EvidenceSlice, RawEvidenceRecord
from skill.evidence.normalize import build_raw_record
from skill.retrieval.models import RetrievalHit


def _make_raw_record(
    *,
    source_id: str,
    title: str,
    url: str,
    snippet: str,
    credibility_tier: str | None,
    route_role: str,
    token_estimate: int,
    **overrides: object,
) -> RawEvidenceRecord:
    hit = RetrievalHit(
        source_id=source_id,
        title=title,
        url=url,
        snippet=snippet,
        credibility_tier=credibility_tier,
    )
    record = build_raw_record(hit=hit, route_role=route_role)
    return replace(record, token_estimate=token_estimate, **overrides)


def _make_canonical(
    *,
    evidence_id: str,
    domain: str = "industry",
    source_id: str = "industry_ddgs",
    title: str | None = None,
    url: str | None = None,
    snippet: str = "Evidence snippet for budget packing tests.",
    credibility_tier: str | None = "industry_news",
    route_role: str = "primary",
    authority: str | None = None,
    jurisdiction: str | None = None,
    jurisdiction_status: str | None = None,
    publication_date: str | None = None,
    effective_date: str | None = None,
    version: str | None = None,
    version_status: str | None = None,
    evidence_level: str | None = None,
    canonical_match_confidence: str | None = None,
    slice_specs: tuple[tuple[str, float, int], ...] = (("default", 0.5, 3),),
) -> CanonicalEvidence:
    title = title or evidence_id.replace("-", " ").title()
    url = url or f"https://example.com/{evidence_id}"
    raw_record = _make_raw_record(
        source_id=source_id,
        title=title,
        url=url,
        snippet=snippet,
        credibility_tier=credibility_tier,
        route_role=route_role,
        token_estimate=sum(spec[2] for spec in slice_specs),
        authority=authority,
        jurisdiction=jurisdiction,
        jurisdiction_status=jurisdiction_status,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
        version_status=version_status,
        evidence_level=evidence_level,
        canonical_match_confidence=canonical_match_confidence,
    )
    slices = tuple(
        EvidenceSlice(
            text=text,
            source_record_id=raw_record.source_id,
            source_span="snippet",
            score=score,
            token_estimate=token_estimate,
        )
        for text, score, token_estimate in slice_specs
    )
    return CanonicalEvidence(
        evidence_id=evidence_id,
        domain=domain,
        canonical_title=title,
        canonical_url=url,
        raw_records=(raw_record,),
        retained_slices=slices,
        linked_variants=(),
        authority=authority,
        jurisdiction=jurisdiction,
        jurisdiction_status=jurisdiction_status,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
        version_status=version_status,
        evidence_level=evidence_level,
        canonical_match_confidence=canonical_match_confidence,
        doi=None,
        arxiv_id=None,
        first_author=None,
        year=None,
        route_role=route_role,
        token_estimate=0,
    )


def test_score_evidence_records_prefers_primary_complete_authoritative_records() -> None:
    from skill.evidence.score import score_evidence_records

    primary_policy = _make_canonical(
        evidence_id="policy-primary",
        domain="policy",
        source_id="policy_official_registry",
        route_role="primary",
        credibility_tier="official_government",
        authority="Ministry of Ecology and Environment",
        jurisdiction="CN",
        jurisdiction_status="observed",
        publication_date="2024-02-15",
        effective_date="2024-03-01",
        version="2024-02",
        version_status="observed",
        slice_specs=(
            ("official high-confidence slice", 0.9, 4),
            ("secondary official slice", 0.5, 2),
        ),
    )
    supplemental_industry = _make_canonical(
        evidence_id="industry-supplemental",
        source_id="industry_ddgs",
        route_role="supplemental",
        credibility_tier="industry_news",
        authority=None,
        publication_date=None,
        slice_specs=(("supporting industry slice", 0.4, 3),),
    )

    ranked = score_evidence_records([supplemental_industry, primary_policy])

    assert [record.evidence_id for record in ranked] == [
        "policy-primary",
        "industry-supplemental",
    ]
    assert getattr(ranked[0], "total_score") > getattr(ranked[1], "total_score")


def test_build_evidence_pack_prunes_low_scoring_retained_slices_before_dropping_records() -> None:
    from skill.evidence.pack import build_evidence_pack
    from skill.evidence.score import score_evidence_records

    primary = _make_canonical(
        evidence_id="primary-record",
        route_role="primary",
        credibility_tier="trusted_news",
        authority="Acme Corp",
        publication_date="2024-04-01",
        slice_specs=(
            ("primary-high", 0.95, 4),
            ("primary-low", 0.10, 3),
        ),
    )
    secondary = _make_canonical(
        evidence_id="secondary-record",
        route_role="primary",
        credibility_tier="trusted_news",
        publication_date="2024-04-02",
        slice_specs=(("secondary", 0.60, 3),),
    )
    overflow = _make_canonical(
        evidence_id="overflow-record",
        route_role="primary",
        credibility_tier="industry_news",
        slice_specs=(("overflow", 0.20, 2),),
    )

    ranked = score_evidence_records([overflow, secondary, primary])
    pack = build_evidence_pack(ranked, token_budget=7, top_k=2)

    assert pack.clipped is True
    assert [record.evidence_id for record in pack.canonical_evidence] == [
        "primary-record",
        "secondary-record",
    ]
    assert [slice_.text for slice_ in pack.canonical_evidence[0].retained_slices] == [
        "primary-high"
    ]
    assert pack.total_token_estimate <= 7


def test_build_evidence_pack_reserves_one_supplemental_item_for_mixed_queries() -> None:
    from skill.evidence.pack import build_evidence_pack
    from skill.evidence.score import score_evidence_records

    primary_best = _make_canonical(
        evidence_id="primary-best",
        route_role="primary",
        credibility_tier="official_government",
        authority="Regulator",
        publication_date="2024-03-01",
        slice_specs=(("primary best", 0.95, 2),),
    )
    primary_second = _make_canonical(
        evidence_id="primary-second",
        route_role="primary",
        credibility_tier="official_government",
        authority="Regulator",
        publication_date="2024-02-01",
        slice_specs=(("primary second", 0.90, 2),),
    )
    supplemental = _make_canonical(
        evidence_id="supplemental-support",
        route_role="supplemental",
        source_id="academic_semantic_scholar",
        domain="academic",
        evidence_level="peer_reviewed",
        canonical_match_confidence="strong_id",
        publication_date="2025-01-01",
        slice_specs=(("supplemental support", 0.50, 2),),
    )

    ranked = score_evidence_records([supplemental, primary_second, primary_best])
    pack = build_evidence_pack(
        ranked,
        token_budget=4,
        top_k=2,
        supplemental_min_items=1,
    )

    assert [record.evidence_id for record in pack.canonical_evidence] == [
        "primary-best",
        "supplemental-support",
    ]
    assert pack.clipped is True


def test_score_evidence_records_are_stable_when_raw_record_order_changes() -> None:
    from skill.evidence.score import score_evidence_records

    high_credibility = _make_raw_record(
        source_id="industry_company",
        title="Industry Merger",
        url="https://company.example/merger",
        snippet="Company confirms the merger details.",
        credibility_tier="company_official",
        route_role="primary",
        token_estimate=5,
    )
    low_credibility = _make_raw_record(
        source_id="industry_blog",
        title="Industry Merger",
        url="https://blog.example/merger",
        snippet="Blog commentary on the merger.",
        credibility_tier="industry_news",
        route_role="primary",
        token_estimate=4,
    )
    slices = (
        EvidenceSlice(
            text="Company confirms the merger details.",
            source_record_id=high_credibility.source_id,
            source_span="snippet",
            score=0.9,
            token_estimate=5,
        ),
    )
    merged = CanonicalEvidence(
        evidence_id="industry-merged",
        domain="industry",
        canonical_title="Industry Merger",
        canonical_url=high_credibility.url,
        raw_records=(high_credibility, low_credibility),
        retained_slices=slices,
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

    reversed_merged = replace(merged, raw_records=(low_credibility, high_credibility))

    scored = score_evidence_records([merged])[0]
    reversed_scored = score_evidence_records([reversed_merged])[0]

    assert getattr(scored, "total_score") == getattr(reversed_scored, "total_score")


def test_build_evidence_pack_keeps_trimmed_high_value_record_over_weaker_one() -> None:
    from skill.evidence.pack import build_evidence_pack
    from skill.evidence.score import score_evidence_records

    strong = _make_canonical(
        evidence_id="strong-record",
        route_role="primary",
        credibility_tier="official_government",
        authority="Regulator",
        publication_date="2024-03-01",
        slice_specs=(
            ("strong-high", 0.95, 4),
            ("strong-low", 0.10, 2),
        ),
    )
    weak = _make_canonical(
        evidence_id="weak-record",
        route_role="primary",
        credibility_tier="industry_news",
        slice_specs=(("weak", 0.20, 3),),
    )

    ranked = score_evidence_records([weak, strong])
    pack = build_evidence_pack(ranked, token_budget=4, top_k=2)

    assert pack.clipped is True
    assert [record.evidence_id for record in pack.canonical_evidence] == ["strong-record"]
    assert [slice_.text for slice_ in pack.canonical_evidence[0].retained_slices] == ["strong-high"]


def test_build_evidence_pack_preserves_metadata_anchored_slice_when_trimming() -> None:
    from skill.evidence.pack import build_evidence_pack
    from skill.evidence.score import score_evidence_records

    policy_record = _make_canonical(
        evidence_id="policy-effective-record",
        domain="policy",
        source_id="policy_official_registry",
        route_role="primary",
        credibility_tier="official_government",
        authority="State Council",
        jurisdiction="CN",
        jurisdiction_status="observed",
        publication_date="2026-04-01",
        effective_date="2026-05-01",
        version="2026-04 edition",
        version_status="observed",
        slice_specs=(
            ("The order modernizes compliance workflows across agencies.", 0.80, 4),
            ("Effective date: 2026-05-01. Version 2026-04 edition.", 0.55, 4),
        ),
    )
    supplemental = _make_canonical(
        evidence_id="supplemental-support",
        domain="industry",
        source_id="industry_ddgs",
        route_role="supplemental",
        credibility_tier="trusted_news",
        slice_specs=(("Industry response summary.", 0.60, 3),),
    )

    ranked = score_evidence_records([supplemental, policy_record])
    pack = build_evidence_pack(ranked, token_budget=7, top_k=2, supplemental_min_items=1)

    assert pack.clipped is True
    assert [record.evidence_id for record in pack.canonical_evidence] == [
        "policy-effective-record",
        "supplemental-support",
    ]
    assert [slice_.text for slice_ in pack.canonical_evidence[0].retained_slices] == [
        "Effective date: 2026-05-01. Version 2026-04 edition."
    ]
