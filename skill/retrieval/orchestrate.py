"""Runtime retrieval orchestration that enforces domain-first prioritization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from skill.evidence.dedupe import collapse_evidence_records
from skill.evidence.normalize import normalize_hit_candidates
from skill.evidence.pack import build_evidence_pack
from skill.evidence.score import score_evidence_records
from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.orchestrator.retrieval_plan import RetrievalPlan
from skill.retrieval.engine import RetrievalExecutionOutcome, run_retrieval
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import prioritize_hits

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]
DEFAULT_EVIDENCE_TOKEN_BUDGET = 48
DEFAULT_EVIDENCE_TOP_K = 4
DEFAULT_SUPPLEMENTAL_MIN_ITEMS = 1


def _shape_results(hits: list[RetrievalHit]) -> list[RetrieveResultItem]:
    return [
        RetrieveResultItem(
            source_id=hit.source_id,
            title=hit.title,
            url=hit.url,
            snippet=hit.snippet,
            credibility_tier=hit.credibility_tier,
        )
        for hit in hits
    ]


def _shape_response(
    plan: RetrievalPlan,
    outcome: RetrievalExecutionOutcome,
    prioritized_hits: list[RetrievalHit],
    *,
    evidence_clipped: bool,
) -> RetrieveResponse:
    return RetrieveResponse(
        route_label=plan.route_label,
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        browser_automation="disabled",
        status=outcome.status,
        failure_reason=outcome.failure_reason,
        gaps=list(outcome.gaps),
        evidence_clipped=evidence_clipped,
        results=_shape_results(prioritized_hits),
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
        outcome=outcome,
        prioritized_hits=prioritized_hits,
        evidence_clipped=evidence_pack.clipped,
    )
