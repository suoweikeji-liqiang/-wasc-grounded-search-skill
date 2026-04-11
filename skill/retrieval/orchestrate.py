"""Runtime retrieval orchestration that enforces domain-first prioritization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.orchestrator.retrieval_plan import RetrievalPlan
from skill.retrieval.engine import RetrievalExecutionOutcome, run_retrieval
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import prioritize_hits

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]


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
) -> RetrieveResponse:
    return RetrieveResponse(
        route_label=plan.route_label,
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        browser_automation="disabled",
        status=outcome.status,
        failure_reason=outcome.failure_reason,
        gaps=list(outcome.gaps),
        results=_shape_results(prioritized_hits),
    )


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
    return _shape_response(plan=plan, outcome=outcome, prioritized_hits=prioritized_hits)
