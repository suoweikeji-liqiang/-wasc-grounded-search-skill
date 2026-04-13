"""Runtime retrieval orchestration that enforces domain-first prioritization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from skill.evidence.models import CanonicalEvidence, EvidencePack
from skill.evidence.dedupe import collapse_evidence_records
from skill.evidence.normalize import normalize_hit_candidates
from skill.evidence.pack import build_evidence_pack
from skill.evidence.score import score_evidence_records
from skill.api.schema import (
    RetrieveCanonicalEvidenceItem,
    RetrieveLinkedVariantItem,
    RetrieveResponse,
    RetrieveResultItem,
    RetrieveRetainedSliceItem,
)
from skill.orchestrator.retrieval_plan import RetrievalPlan
from skill.retrieval.engine import RetrievalExecutionOutcome, run_retrieval
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import prioritize_hits

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]
DEFAULT_EVIDENCE_TOKEN_BUDGET = 48
DEFAULT_EVIDENCE_TOP_K = 4
DEFAULT_SUPPLEMENTAL_MIN_ITEMS = 1
_INDUSTRY_CREDIBILITY_PRIORITY: dict[str | None, int] = {
    "company_official": 0,
    "industry_association": 1,
    "trusted_news": 2,
    "general_web": 3,
    None: 4,
}


def _best_snippet(record: CanonicalEvidence) -> str:
    if record.retained_slices:
        best_slice = max(
            record.retained_slices,
            key=lambda slice_: (slice_.score, -slice_.token_estimate, slice_.text),
        )
        return best_slice.text
    return record.raw_records[0].snippet


def _industry_query_match_score(query: str, record: CanonicalEvidence) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join(
        [
            record.canonical_title,
            *[slice_.text for slice_ in record.retained_slices],
        ]
    ).lower()
    return sum(1 for token in tokens if token in haystack)


def _order_records_for_response(
    *,
    plan: RetrievalPlan,
    query: str,
    records: tuple[CanonicalEvidence, ...],
) -> tuple[CanonicalEvidence, ...]:
    if plan.route_label != "industry":
        return records

    ordered = sorted(
        records,
        key=lambda record: (
            -_industry_query_match_score(query, record),
            _INDUSTRY_CREDIBILITY_PRIORITY.get(
                record.raw_records[0].credibility_tier,
                99,
            ),
            record.evidence_id,
        ),
    )
    return tuple(ordered)


def _shape_results(records: tuple[CanonicalEvidence, ...]) -> list[RetrieveResultItem]:
    return [
        RetrieveResultItem(
            source_id=record.raw_records[0].source_id,
            title=record.canonical_title,
            url=record.canonical_url,
            snippet=_best_snippet(record),
            credibility_tier=record.raw_records[0].credibility_tier,
        )
        for record in records
    ]


def _shape_canonical_evidence(
    records: tuple[CanonicalEvidence, ...],
) -> list[RetrieveCanonicalEvidenceItem]:
    return [
        RetrieveCanonicalEvidenceItem(
            evidence_id=record.evidence_id,
            domain=record.domain,
            canonical_title=record.canonical_title,
            canonical_url=record.canonical_url,
            route_role=record.route_role,
            authority=record.authority,
            jurisdiction=record.jurisdiction,
            jurisdiction_status=record.jurisdiction_status,
            publication_date=record.publication_date,
            effective_date=record.effective_date,
            version=record.version,
            version_status=record.version_status,
            evidence_level=record.evidence_level,
            canonical_match_confidence=record.canonical_match_confidence,
            doi=record.doi,
            arxiv_id=record.arxiv_id,
            first_author=record.first_author,
            year=record.year,
            retained_slices=[
                RetrieveRetainedSliceItem(
                    text=slice_.text,
                    source_record_id=slice_.source_record_id,
                    source_span=slice_.source_span,
                )
                for slice_ in record.retained_slices
            ],
            linked_variants=[
                RetrieveLinkedVariantItem(
                    source_id=variant.source_id,
                    title=variant.title,
                    url=variant.url,
                    variant_type=variant.variant_type,
                    canonical_match_confidence=variant.canonical_match_confidence,
                    doi=variant.doi,
                    arxiv_id=variant.arxiv_id,
                    first_author=variant.first_author,
                    year=variant.year,
                )
                for variant in record.linked_variants
            ],
        )
        for record in records
    ]


def _shape_response(
    plan: RetrievalPlan,
    query: str,
    outcome: RetrievalExecutionOutcome,
    evidence_pack: EvidencePack,
) -> RetrieveResponse:
    ordered_records = _order_records_for_response(
        plan=plan,
        query=query,
        records=evidence_pack.canonical_evidence,
    )
    return RetrieveResponse(
        route_label=plan.route_label,
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        browser_automation="disabled",
        status=outcome.status,
        failure_reason=outcome.failure_reason,
        gaps=list(outcome.gaps),
        canonical_evidence=_shape_canonical_evidence(ordered_records),
        evidence_clipped=evidence_pack.clipped,
        evidence_pruned=evidence_pack.pruned,
        results=_shape_results(ordered_records),
    )


def _route_role_by_source(plan: RetrievalPlan) -> dict[str, str]:
    route_roles: dict[str, str] = {}
    for step in (*plan.first_wave_sources, *plan.fallback_sources):
        if step.source.is_supplemental:
            route_roles[step.source.source_id] = "supplemental"
    return route_roles


async def execute_retrieval_pipeline(
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
) -> RetrieveResponse:
    """Run retrieval, enforce domain-priority ordering, then shape API response."""
    outcome = await run_retrieval(
        plan=plan,
        query=query,
        adapter_registry=adapter_registry,
    )
    prioritized_hits = prioritize_hits(
        domain=plan.route_label,
        hits=list(outcome.results),
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        query=query,
    )
    normalized_records = normalize_hit_candidates(
        hits=prioritized_hits,
        route_role_by_source=_route_role_by_source(plan),
    )
    canonical_records = collapse_evidence_records(normalized_records)
    scored_records = score_evidence_records(canonical_records)
    evidence_pack = build_evidence_pack(
        scored_records,
        token_budget=DEFAULT_EVIDENCE_TOKEN_BUDGET,
        top_k=DEFAULT_EVIDENCE_TOP_K,
        supplemental_min_items=DEFAULT_SUPPLEMENTAL_MIN_ITEMS,
    )
    return _shape_response(
        plan=plan,
        query=query,
        outcome=outcome,
        evidence_pack=evidence_pack,
    )
