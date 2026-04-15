"""Runtime retrieval orchestration that enforces domain-first prioritization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass

from skill.evidence.models import CanonicalEvidence, EvidencePack
from skill.config.retrieval import SOURCE_BACKUP_CHAIN
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
from skill.retrieval.priority import prioritize_hits, score_query_alignment

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]
DEFAULT_EVIDENCE_TOKEN_BUDGET = 256
DEFAULT_EVIDENCE_TOP_K = 6
DEFAULT_SUPPLEMENTAL_MIN_ITEMS = 2
_INDUSTRY_CREDIBILITY_PRIORITY: dict[str | None, int] = {
    "company_official": 0,
    "industry_association": 1,
    "trusted_news": 2,
    "general_web": 3,
    None: 4,
}
_LAST_RETRIEVAL_TRACE: ContextVar[tuple[dict[str, object], ...]] = ContextVar(
    "last_retrieval_trace",
    default=(),
)


@dataclass(frozen=True)
class RetrievalPipelineExecution:
    response: RetrieveResponse
    retrieval_trace: tuple[dict[str, object], ...]


def clear_last_retrieval_trace() -> None:
    _LAST_RETRIEVAL_TRACE.set(())


def consume_last_retrieval_trace() -> tuple[dict[str, object], ...]:
    trace = _LAST_RETRIEVAL_TRACE.get()
    _LAST_RETRIEVAL_TRACE.set(())
    return trace


def _best_snippet(record: CanonicalEvidence) -> str:
    if record.retained_slices:
        best_slice = max(
            record.retained_slices,
            key=lambda slice_: (slice_.score, -slice_.token_estimate, slice_.text),
        )
        return best_slice.text
    return record.raw_records[0].snippet


def _query_match_score(query: str, record: CanonicalEvidence) -> int:
    route = record.domain if record.domain in {"policy", "industry", "academic"} else "industry"
    return score_query_alignment(
        query,
        route=route,  # type: ignore[arg-type]
        title=record.canonical_title,
        snippet=" ".join(slice_.text for slice_ in record.retained_slices),
        url=record.canonical_url,
        authority=record.authority,
        publication_date=record.publication_date,
        effective_date=record.effective_date,
        version=record.version,
        year=record.year,
    )


def _route_role_by_target_route(plan: RetrievalPlan) -> dict[str, str]:
    route_role_by_target_route = {plan.primary_route: "primary"}
    if plan.supplemental_route is not None:
        route_role_by_target_route[plan.supplemental_route] = "supplemental"
    return route_role_by_target_route


def _record_variant_pairs(record: CanonicalEvidence) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for raw_record in record.raw_records:
        for reason_code, variant_query in zip(
            raw_record.variant_reason_codes,
            raw_record.variant_queries,
            strict=False,
        ):
            pair = (reason_code, variant_query)
            if pair not in pairs:
                pairs.append(pair)
    return tuple(pairs)


def _record_focus_queries(record: CanonicalEvidence) -> tuple[str, ...]:
    variant_pairs = _record_variant_pairs(record)
    return tuple(
        dict.fromkeys(
            query
            for reason_code, query in variant_pairs
            if reason_code != "original"
        )
    )


def _record_route_query_match_score(
    *,
    record: CanonicalEvidence,
    route: str,
) -> int:
    focus_queries = _record_focus_queries(record)
    if not focus_queries:
        return 0
    return max(
        score_query_alignment(
            focus_query,
            route=route,  # type: ignore[arg-type]
            title=record.canonical_title,
            snippet=" ".join(slice_.text for slice_ in record.retained_slices),
            url=record.canonical_url,
            authority=record.authority,
            publication_date=record.publication_date,
            effective_date=record.effective_date,
            version=record.version,
            year=record.year,
        )
        for focus_query in focus_queries
    )


def _mixed_route_query_match_score(
    *,
    plan: RetrievalPlan,
    record: CanonicalEvidence,
) -> int:
    route = plan.primary_route if record.route_role == "primary" else plan.supplemental_route
    if route is None:
        return 0
    return _record_route_query_match_score(record=record, route=route)


def _interleave_mixed_records(
    primary_records: list[CanonicalEvidence],
    supplemental_records: list[CanonicalEvidence],
    other_records: list[CanonicalEvidence],
) -> tuple[CanonicalEvidence, ...]:
    ordered: list[CanonicalEvidence] = []
    if primary_records:
        ordered.append(primary_records[0])
    if supplemental_records:
        ordered.append(supplemental_records[0])
    ordered.extend(primary_records[1:])
    ordered.extend(supplemental_records[1:])
    ordered.extend(other_records)
    return tuple(ordered)


def _best_mixed_route_record(
    records: list[CanonicalEvidence],
    *,
    plan: RetrievalPlan,
    query: str,
    route_role: str,
) -> CanonicalEvidence | None:
    candidates = [record for record in records if record.route_role == route_role]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda record: (
            -_mixed_route_query_match_score(plan=plan, record=record),
            -_query_match_score(query, record),
            -getattr(record, "total_score", 0.0),
            record.evidence_id,
        ),
    )
    best = ranked[0]
    if (
        _mixed_route_query_match_score(plan=plan, record=best) <= 0
        and _query_match_score(query, best) <= 0
    ):
        return None
    return best


def _seed_mixed_coverage_records(
    *,
    plan: RetrievalPlan,
    query: str,
    records: list[CanonicalEvidence],
    top_k: int,
) -> list[CanonicalEvidence]:
    if plan.route_label != "mixed" or plan.supplemental_route is None or len(records) <= top_k:
        return records

    best_primary = _best_mixed_route_record(
        records,
        plan=plan,
        query=query,
        route_role="primary",
    )
    best_supplemental = _best_mixed_route_record(
        records,
        plan=plan,
        query=query,
        route_role="supplemental",
    )
    if best_primary is None or best_supplemental is None:
        return records

    seeded: list[CanonicalEvidence] = [best_primary]
    if best_supplemental.evidence_id != best_primary.evidence_id:
        seeded.append(best_supplemental)

    selected_ids = {record.evidence_id for record in seeded}
    for record in records:
        if record.evidence_id in selected_ids:
            continue
        seeded.append(record)
        selected_ids.add(record.evidence_id)
        if len(seeded) == top_k:
            break

    return seeded


def _order_records_for_response(
    *,
    plan: RetrievalPlan,
    query: str,
    records: tuple[CanonicalEvidence, ...],
) -> tuple[CanonicalEvidence, ...]:
    if plan.route_label == "mixed":
        primary_records = [
            record for record in records if record.route_role == "primary"
        ]
        supplemental_records = [
            record for record in records if record.route_role == "supplemental"
        ]
        other_records = [
            record
            for record in records
            if record.route_role not in {"primary", "supplemental"}
        ]
        ordered_primary = sorted(
            primary_records,
            key=lambda record: (
                -_mixed_route_query_match_score(plan=plan, record=record),
                -_query_match_score(query, record),
                -getattr(record, "total_score", 0.0),
                record.evidence_id,
            ),
        )
        ordered_supplemental = sorted(
            supplemental_records,
            key=lambda record: (
                -_mixed_route_query_match_score(plan=plan, record=record),
                -_query_match_score(query, record),
                -getattr(record, "total_score", 0.0),
                record.evidence_id,
            ),
        )
        return _interleave_mixed_records(
            ordered_primary,
            ordered_supplemental,
            other_records,
        )

    if plan.route_label in {"policy", "academic"}:
        ordered = sorted(
            records,
            key=lambda record: (
                -_query_match_score(query, record),
                -getattr(record, "total_score", 0.0),
                record.evidence_id,
            ),
        )
        return tuple(ordered)

    if plan.route_label != "industry":
        return records

    ordered = sorted(
        records,
        key=lambda record: (
            -_query_match_score(query, record),
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
    if plan.primary_route == "industry":
        route_roles.setdefault("industry_ddgs", "primary")
    elif plan.supplemental_route == "industry":
        route_roles.setdefault("industry_ddgs", "supplemental")
    return route_roles


async def execute_retrieval_pipeline(
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
) -> RetrieveResponse:
    """Backward-compatible wrapper returning the public response only."""
    clear_last_retrieval_trace()
    try:
        execution = await execute_retrieval_pipeline_with_trace(
            plan=plan,
            query=query,
            adapter_registry=adapter_registry,
        )
    except BaseException:
        clear_last_retrieval_trace()
        raise
    _LAST_RETRIEVAL_TRACE.set(execution.retrieval_trace)
    return execution.response


async def execute_retrieval_pipeline_with_trace(
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
) -> RetrievalPipelineExecution:
    """Run retrieval, enforce domain-priority ordering, and retain internal trace."""
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
        route_role_by_target_route=_route_role_by_target_route(plan),
    )
    canonical_records = collapse_evidence_records(normalized_records)
    scored_records = score_evidence_records(canonical_records)
    ordered_for_pack = list(
        _order_records_for_response(
            plan=plan,
            query=query,
            records=tuple(scored_records),
        )
    )
    pack_input_records = _seed_mixed_coverage_records(
        plan=plan,
        query=query,
        records=ordered_for_pack,
        top_k=DEFAULT_EVIDENCE_TOP_K,
    )
    evidence_pack = build_evidence_pack(
        pack_input_records,
        token_budget=DEFAULT_EVIDENCE_TOKEN_BUDGET,
        top_k=DEFAULT_EVIDENCE_TOP_K,
        supplemental_min_items=DEFAULT_SUPPLEMENTAL_MIN_ITEMS,
    )
    return RetrievalPipelineExecution(
        response=_shape_response(
            plan=plan,
            query=query,
            outcome=outcome,
            evidence_pack=evidence_pack,
        ),
        retrieval_trace=tuple(
            {
                "source_id": source_result.source_id,
                "stage": source_result.stage,
                "started_at_ms": source_result.started_at_ms,
                "elapsed_ms": source_result.elapsed_ms,
                "hit_count": len(source_result.hits),
                "failure_reason": source_result.failure_reason,
                "gaps": list(source_result.gaps),
                "error_class": source_result.error_class,
                "planner_backup_source_id": (
                    SOURCE_BACKUP_CHAIN.get(source_result.source_id, {}).get(
                        source_result.failure_reason or ""
                    )
                    if source_result.status != "success"
                    else None
                ),
                "was_cancelled_by_deadline": source_result.was_cancelled_by_deadline,
            }
            for source_result in outcome.source_results
        ),
    )
