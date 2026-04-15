"""Phase 4 citation-check and uncertainty regressions."""

from __future__ import annotations

from skill.evidence.models import CanonicalEvidence, EvidenceSlice
from skill.evidence.normalize import build_raw_record
from skill.retrieval.models import RetrievalHit
from skill.synthesis.citation_check import validate_answer_citations
from skill.synthesis.models import ClaimCitation, KeyPoint, SourceReference, StructuredAnswerDraft
from skill.synthesis.uncertainty import build_uncertainty_notes


def _policy_canonical(*, incomplete: bool = False) -> CanonicalEvidence:
    raw_record = build_raw_record(
        RetrievalHit(
            source_id="policy_official_registry",
            title="Climate Order 2026",
            url="https://www.gov.cn/policy/climate-order-2026",
            snippet="The Climate Order takes effect on May 1, 2026.",
            credibility_tier="official_government",
            authority="State Council",
            jurisdiction=None if incomplete else "CN",
            publication_date="2026-04-01",
            effective_date="2026-05-01",
            version=None if incomplete else "2026-04 edition",
        ),
        route_role="primary",
    )
    return CanonicalEvidence(
        evidence_id="policy-1",
        domain="policy",
        canonical_title="Climate Order 2026",
        canonical_url="https://www.gov.cn/policy/climate-order-2026",
        raw_records=(raw_record,),
        retained_slices=(
            EvidenceSlice(
                text="The Climate Order takes effect on May 1, 2026.",
                source_record_id="policy-1-slice-1",
                source_span="snippet",
                score=1.0,
                token_estimate=8,
            ),
        ),
        authority="State Council",
        jurisdiction=None if incomplete else "CN",
        jurisdiction_status="jurisdiction_unknown" if incomplete else "observed",
        publication_date="2026-04-01",
        effective_date="2026-05-01",
        version=None if incomplete else "2026-04 edition",
        version_status="version_missing" if incomplete else "observed",
        route_role="primary",
    )


def _academic_canonical() -> CanonicalEvidence:
    raw_record = build_raw_record(
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Grounded Search Evidence Packing",
            url="https://doi.org/10.1000/evidence-packing",
            snippet="The paper proposes evidence packing with bounded context windows.",
            credibility_tier="peer_reviewed",
            doi="10.1000/evidence-packing",
            arxiv_id="2604.12345",
            first_author="Lin",
            year=2026,
            evidence_level="peer_reviewed",
        ),
        route_role="supplemental",
    )
    return CanonicalEvidence(
        evidence_id="paper-1",
        domain="academic",
        canonical_title="Grounded Search Evidence Packing",
        canonical_url="https://doi.org/10.1000/evidence-packing",
        raw_records=(raw_record,),
        retained_slices=(
            EvidenceSlice(
                text="The paper proposes evidence packing with bounded context windows.",
                source_record_id="paper-1-slice-1",
                source_span="snippet",
                score=0.9,
                token_estimate=9,
            ),
        ),
        evidence_level="peer_reviewed",
        canonical_match_confidence="heuristic",
        doi="10.1000/evidence-packing",
        arxiv_id="2604.12345",
        first_author="Lin",
        year=2026,
        route_role="supplemental",
    )


def _draft_with_citation(citation: ClaimCitation) -> StructuredAnswerDraft:
    return StructuredAnswerDraft(
        conclusion="The Climate Order takes effect on May 1, 2026.",
        key_points=[
            KeyPoint(
                key_point_id="kp-1",
                statement="The Climate Order takes effect on May 1, 2026.",
                citations=[citation],
            )
        ],
        sources=[
            SourceReference(
                evidence_id="policy-1",
                title="Climate Order 2026",
                url="https://www.gov.cn/policy/climate-order-2026",
            )
        ],
        uncertainty_notes=[],
        gaps=[],
    )


def test_validate_answer_citations_accepts_valid_evidence_binding() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="policy-1",
            source_record_id="policy-1-slice-1",
            source_url="https://www.gov.cn/policy/climate-order-2026",
            quote_text="The Climate Order takes effect on May 1, 2026.",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 1
    assert result.total_key_point_count == 1
    assert result.issues == ()
    assert len(result.validated_key_points) == 1


def test_validate_answer_citations_rejects_unknown_evidence_id() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="missing-policy",
            source_record_id="policy-1-slice-1",
            source_url="https://www.gov.cn/policy/climate-order-2026",
            quote_text="The Climate Order takes effect on May 1, 2026.",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 0
    assert any("missing evidence_id" in issue for issue in result.issues)


def test_validate_answer_citations_rejects_unknown_source_record_id() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="policy-1",
            source_record_id="missing-slice",
            source_url="https://www.gov.cn/policy/climate-order-2026",
            quote_text="The Climate Order takes effect on May 1, 2026.",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 0
    assert any("missing source_record_id" in issue for issue in result.issues)


def test_validate_answer_citations_rejects_quote_mismatch() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="policy-1",
            source_record_id="policy-1-slice-1",
            source_url="https://www.gov.cn/policy/climate-order-2026",
            quote_text="The Climate Order starts in June.",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 0
    assert any("quote_text" in issue for issue in result.issues)


def test_validate_answer_citations_backfills_quote_text_and_source_url() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="policy-1",
            source_record_id="policy-1-slice-1",
            source_url="",
            quote_text="",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 1
    validated_citation = result.validated_key_points[0].citations[0]
    assert validated_citation.source_url == "https://www.gov.cn/policy/climate-order-2026"
    assert validated_citation.quote_text == "The Climate Order takes effect on May 1, 2026."


def test_validate_answer_citations_accepts_normalized_quote_match() -> None:
    draft = _draft_with_citation(
        ClaimCitation(
            evidence_id="policy-1",
            source_record_id="policy-1-slice-1",
            source_url="https://www.gov.cn/policy/climate-order-2026",
            quote_text="The Climate Order takes effect on May 1 2026",
        )
    )

    result = validate_answer_citations(draft, (_policy_canonical(),))

    assert result.grounded_key_point_count == 1
    assert result.issues == ()


def test_build_uncertainty_notes_uses_required_prefixes() -> None:
    notes = build_uncertainty_notes(
        retrieval_status="partial",
        gaps=("Only one peer-reviewed source was retained.",),
        evidence_clipped=True,
        evidence_pruned=False,
        canonical_evidence=(_policy_canonical(incomplete=True), _academic_canonical()),
        citation_issues=("kp-2 missing evidence_id",),
    )

    assert any(note.startswith("Evidence clipped:") for note in notes)
    assert any(note.startswith("Retrieval gaps:") for note in notes)
    assert any(note.startswith("Policy metadata incomplete:") for note in notes)
    assert any(note.startswith("Academic match heuristic:") for note in notes)
    assert any(note.startswith("Citation validation:") for note in notes)
