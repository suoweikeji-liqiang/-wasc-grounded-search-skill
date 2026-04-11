"""Runtime retrieval execution with first-wave concurrency and hard budgets."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from skill.orchestrator.retrieval_plan import PlannedSourceStep, RetrievalPlan
from skill.retrieval.models import (
    RetrievalFailureReason,
    RetrievalHit,
    RetrievalStatus,
    SourceExecutionResult,
)

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]


@dataclass(frozen=True)
class RetrievalExecutionOutcome:
    status: RetrievalStatus
    failure_reason: RetrievalFailureReason | None
    gaps: tuple[str, ...]
    results: tuple[RetrievalHit, ...]
    source_results: tuple[SourceExecutionResult, ...]


def _map_exception_to_failure_reason(exc: BaseException) -> RetrievalFailureReason:
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"

    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return "rate_limited"
    return "adapter_error"


def _normalize_hits(raw_hits: list[RetrievalHit], source_id: str) -> tuple[RetrievalHit, ...]:
    normalized: list[RetrievalHit] = []
    for hit in raw_hits:
        if isinstance(hit, RetrievalHit):
            normalized.append(hit)
            continue

        if not isinstance(hit, Mapping):
            raise TypeError(f"Adapter '{source_id}' returned unsupported hit payload type")

        normalized.append(
            RetrievalHit(
                source_id=str(hit.get("source_id", source_id)),
                title=str(hit["title"]),
                url=str(hit["url"]),
                snippet=str(hit["snippet"]),
                credibility_tier=(
                    str(hit["credibility_tier"])
                    if hit.get("credibility_tier") is not None
                    else None
                ),
            )
        )
    return tuple(normalized)


async def _run_single_source(
    step: PlannedSourceStep,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    semaphore: asyncio.Semaphore,
    per_source_timeout_seconds: float,
) -> SourceExecutionResult:
    source_id = step.source.source_id
    adapter = adapter_registry.get(source_id)
    if adapter is None:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(source_id,),
        )

    async with semaphore:
        try:
            raw_hits = await asyncio.wait_for(
                adapter(query),
                timeout=per_source_timeout_seconds,
            )
        except BaseException as exc:
            return SourceExecutionResult(
                source_id=source_id,
                status="failure_gaps",
                failure_reason=_map_exception_to_failure_reason(exc),
                gaps=(source_id,),
            )

    if not raw_hits:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="no_hits",
            gaps=(source_id,),
        )

    hits = _normalize_hits(raw_hits=raw_hits, source_id=source_id)
    return SourceExecutionResult(
        source_id=source_id,
        status="success",
        hits=hits,
    )


def _build_outcome(
    ordered_results: tuple[SourceExecutionResult, ...],
) -> RetrievalExecutionOutcome:
    hits: list[RetrievalHit] = []
    gaps: list[str] = []
    first_failure: RetrievalFailureReason | None = None
    has_success = False
    has_failure = False

    for source_result in ordered_results:
        if source_result.status == "success":
            has_success = True
            hits.extend(source_result.hits)
            continue

        has_failure = True
        gaps.extend(source_result.gaps)
        if first_failure is None:
            first_failure = source_result.failure_reason

    if has_success and not has_failure:
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(hits),
            source_results=ordered_results,
        )

    if has_success and has_failure:
        return RetrievalExecutionOutcome(
            status="partial",
            failure_reason=first_failure,
            gaps=tuple(dict.fromkeys(gaps)),
            results=tuple(hits),
            source_results=ordered_results,
        )

    return RetrievalExecutionOutcome(
        status="failure_gaps",
        failure_reason=first_failure or "adapter_error",
        gaps=tuple(dict.fromkeys(gaps)),
        results=(),
        source_results=ordered_results,
    )


async def run_retrieval(
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
) -> RetrievalExecutionOutcome:
    """Run first-wave retrieval with hard per-source and overall budgets."""
    first_wave_steps = plan.first_wave_sources
    if not first_wave_steps:
        return RetrievalExecutionOutcome(
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=("first_wave_sources_missing",),
            results=(),
            source_results=(),
        )

    semaphore = asyncio.Semaphore(max(1, plan.global_concurrency_cap))
    tasks: dict[asyncio.Task[SourceExecutionResult], str] = {}

    for step in first_wave_steps:
        task = asyncio.create_task(
            _run_single_source(
                step=step,
                query=query,
                adapter_registry=adapter_registry,
                semaphore=semaphore,
                per_source_timeout_seconds=plan.per_source_timeout_seconds,
            )
        )
        tasks[task] = step.source.source_id

    done, pending = await asyncio.wait(
        tuple(tasks.keys()),
        timeout=plan.overall_deadline_seconds,
    )

    for pending_task in pending:
        pending_task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    by_source: dict[str, SourceExecutionResult] = {}
    for done_task in done:
        source_id = tasks[done_task]
        try:
            by_source[source_id] = done_task.result()
        except BaseException as exc:
            by_source[source_id] = SourceExecutionResult(
                source_id=source_id,
                status="failure_gaps",
                failure_reason=_map_exception_to_failure_reason(exc),
                gaps=(source_id,),
            )

    for pending_task in pending:
        source_id = tasks[pending_task]
        by_source[source_id] = SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="timeout",
            gaps=(source_id,),
        )

    ordered_results = tuple(
        by_source.get(step.source.source_id)
        or SourceExecutionResult(
            source_id=step.source.source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(step.source.source_id,),
        )
        for step in first_wave_steps
    )
    return _build_outcome(ordered_results=ordered_results)
