"""Runtime retrieval execution with first-wave concurrency and hard budgets."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from skill.orchestrator.retrieval_plan import PlannedSourceStep, RetrievalPlan
from skill.retrieval.fallback_fsm import (
    map_exception_to_failure_reason,
)
from skill.retrieval.models import (
    RetrievalFailureReason,
    RetrievalHit,
    RetrievalStatus,
    SourceExecutionResult,
)
from skill.retrieval.query_variants import build_query_variants

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]


def _optional_str_field(hit: Mapping[str, Any], field_name: str) -> str | None:
    value = hit.get(field_name)
    if value in (None, ""):
        return None
    return str(value)


def _optional_int_field(hit: Mapping[str, Any], field_name: str) -> int | None:
    value = hit.get(field_name)
    if value in (None, ""):
        return None
    return int(value)


@dataclass(frozen=True)
class RetrievalExecutionOutcome:
    status: RetrievalStatus
    failure_reason: RetrievalFailureReason | None
    gaps: tuple[str, ...]
    results: tuple[RetrievalHit, ...]
    source_results: tuple[SourceExecutionResult, ...]


def _normalize_hits(raw_hits: list[Any], source_id: str) -> tuple[RetrievalHit, ...]:
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
                credibility_tier=_optional_str_field(hit, "credibility_tier"),
                authority=_optional_str_field(hit, "authority"),
                jurisdiction=_optional_str_field(hit, "jurisdiction"),
                publication_date=_optional_str_field(hit, "publication_date"),
                effective_date=_optional_str_field(hit, "effective_date"),
                version=_optional_str_field(hit, "version"),
                doi=_optional_str_field(hit, "doi"),
                arxiv_id=_optional_str_field(hit, "arxiv_id"),
                first_author=_optional_str_field(hit, "first_author"),
                year=_optional_int_field(hit, "year"),
                evidence_level=_optional_str_field(hit, "evidence_level"),
            )
        )
    return tuple(normalized)


def _dedupe_hits(hits: list[RetrievalHit]) -> tuple[RetrievalHit, ...]:
    deduped: list[RetrievalHit] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in hits:
        key = (
            hit.source_id,
            hit.url.strip().lower(),
            hit.title.strip().lower(),
        )
        if key in seen:
            continue
        deduped.append(hit)
        seen.add(key)
    return tuple(deduped)


async def _run_single_source(
    source_id: str,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    timeout_seconds: float,
) -> SourceExecutionResult:
    adapter = adapter_registry.get(source_id)
    if adapter is None:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(source_id,),
        )

    if timeout_seconds <= 0:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="timeout",
            gaps=(source_id,),
        )

    async def _invoke_adapter() -> list[Any]:
        return await asyncio.wait_for(
            adapter(query),
            timeout=timeout_seconds,
        )

    try:
        raw_hits = await _invoke_adapter()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason=map_exception_to_failure_reason(exc),
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


async def _run_source_variants(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    deadline_at: float,
) -> SourceExecutionResult:
    source_id = step.source.source_id
    variants = build_query_variants(
        query=query,
        route_label=plan.route_label,
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        target_route=step.source.route,
        variant_limit=plan.query_variant_budget,
    )

    loop = asyncio.get_running_loop()
    merged_hits: list[RetrievalHit] = []
    last_failure_reason: RetrievalFailureReason = "no_hits"

    for variant in variants:
        remaining = deadline_at - loop.time()
        if remaining <= 0:
            break

        attempt = await _run_single_source(
            source_id=source_id,
            query=variant.query,
            adapter_registry=adapter_registry,
            timeout_seconds=remaining,
        )
        if attempt.status == "success":
            merged_hits.extend(attempt.hits)
            continue

        failure_reason = attempt.failure_reason or "adapter_error"
        if failure_reason == "no_hits":
            last_failure_reason = failure_reason
            continue

        if merged_hits:
            return SourceExecutionResult(
                source_id=source_id,
                status="success",
                hits=_dedupe_hits(merged_hits),
            )

        return attempt

    if merged_hits:
        return SourceExecutionResult(
            source_id=source_id,
            status="success",
            hits=_dedupe_hits(merged_hits),
        )

    if loop.time() >= deadline_at:
        last_failure_reason = "timeout"

    return SourceExecutionResult(
        source_id=source_id,
        status="failure_gaps",
        failure_reason=last_failure_reason,
        gaps=(source_id,),
    )


async def _run_source_step(
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    timeout_seconds: float,
    semaphore: asyncio.Semaphore | None = None,
) -> SourceExecutionResult:
    loop = asyncio.get_running_loop()
    deadline_at = loop.time() + max(0.0, timeout_seconds)
    if semaphore is None:
        return await _run_source_variants(
            step=step,
            plan=plan,
            query=query,
            adapter_registry=adapter_registry,
            deadline_at=deadline_at,
        )

    remaining = deadline_at - loop.time()
    if remaining <= 0:
        return SourceExecutionResult(
            source_id=step.source.source_id,
            status="failure_gaps",
            failure_reason="timeout",
            gaps=(step.source.source_id,),
        )
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=remaining)
    except asyncio.TimeoutError:
        return SourceExecutionResult(
            source_id=step.source.source_id,
            status="failure_gaps",
            failure_reason="timeout",
            gaps=(step.source.source_id,),
        )
    try:
        return await _run_source_variants(
            step=step,
            plan=plan,
            query=query,
            adapter_registry=adapter_registry,
            deadline_at=deadline_at,
        )
    finally:
        semaphore.release()


async def _run_first_wave(
    plan: RetrievalPlan,
    first_wave_steps: tuple[PlannedSourceStep, ...],
    query: str,
    adapter_registry: Mapping[str, Adapter],
    per_source_timeout_seconds: float,
    overall_timeout_seconds: float,
    concurrency_cap: int,
) -> dict[str, SourceExecutionResult]:
    semaphore = asyncio.Semaphore(max(1, concurrency_cap))
    tasks: dict[asyncio.Task[SourceExecutionResult], str] = {}

    for step in first_wave_steps:
        source_id = step.source.source_id
        task = asyncio.create_task(
            _run_source_step(
                step=step,
                plan=plan,
                query=query,
                adapter_registry=adapter_registry,
                timeout_seconds=per_source_timeout_seconds,
                semaphore=semaphore,
            )
        )
        tasks[task] = source_id

    done, pending = await asyncio.wait(
        tuple(tasks.keys()),
        timeout=max(0.0, overall_timeout_seconds),
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
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            by_source[source_id] = SourceExecutionResult(
                source_id=source_id,
                status="failure_gaps",
                failure_reason=map_exception_to_failure_reason(exc),
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

    return by_source


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

    loop = asyncio.get_running_loop()
    deadline_at = loop.time() + max(0.0, plan.overall_deadline_seconds)
    first_wave_results = await _run_first_wave(
        plan=plan,
        first_wave_steps=first_wave_steps,
        query=query,
        adapter_registry=adapter_registry,
        per_source_timeout_seconds=max(0.0, plan.per_source_timeout_seconds),
        overall_timeout_seconds=max(0.0, deadline_at - loop.time()),
        concurrency_cap=plan.global_concurrency_cap,
    )
    allowed_fallback_transitions: dict[tuple[str, RetrievalFailureReason], PlannedSourceStep] = {}
    for fallback_step in plan.fallback_sources:
        fallback_from_source_id = fallback_step.fallback_from_source_id
        if fallback_from_source_id is None:
            continue
        for trigger_reason in fallback_step.trigger_on_failures:
            transition_key = (fallback_from_source_id, trigger_reason)
            allowed_fallback_transitions.setdefault(
                transition_key,
                fallback_step,
            )

    all_attempt_results: list[SourceExecutionResult] = []
    final_hits: list[RetrievalHit] = []
    unresolved_reasons: list[RetrievalFailureReason] = []
    unresolved_gaps: list[str] = []

    for step in first_wave_steps:
        source_id = step.source.source_id
        primary_result = first_wave_results.get(source_id) or SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(source_id,),
        )
        all_attempt_results.append(primary_result)

        if primary_result.status == "success":
            final_hits.extend(primary_result.hits)
            continue

        chain_gaps: list[str] = list(primary_result.gaps)
        failure_reason = primary_result.failure_reason or "adapter_error"
        current_source = source_id
        visited_sources: set[str] = {source_id}
        recovered = False

        while True:
            remaining = deadline_at - loop.time()
            if remaining <= 0:
                failure_reason = "timeout"
                break

            fallback_step = allowed_fallback_transitions.get(
                (current_source, failure_reason)
            )
            if fallback_step is None:
                break

            fallback_source_id = fallback_step.source.source_id
            if fallback_source_id in visited_sources:
                break

            visited_sources.add(fallback_source_id)
            fallback_result = await _run_source_step(
                step=fallback_step,
                plan=plan,
                query=query,
                adapter_registry=adapter_registry,
                timeout_seconds=min(plan.per_source_timeout_seconds, remaining),
            )
            all_attempt_results.append(fallback_result)

            if fallback_result.status == "success":
                final_hits.extend(fallback_result.hits)
                recovered = True
                break

            chain_gaps.extend(fallback_result.gaps)
            failure_reason = fallback_result.failure_reason or "adapter_error"
            current_source = fallback_source_id

        if not recovered:
            unresolved_reasons.append(failure_reason)
            unresolved_gaps.extend(chain_gaps)

    deduped_gaps = tuple(dict.fromkeys(unresolved_gaps))

    if final_hits and not unresolved_reasons:
        status: RetrievalStatus = "success"
        failure_reason: RetrievalFailureReason | None = None
    elif final_hits:
        status = "partial"
        failure_reason = unresolved_reasons[0]
    else:
        status = "failure_gaps"
        failure_reason = unresolved_reasons[0] if unresolved_reasons else "adapter_error"

    return RetrievalExecutionOutcome(
        status=status,
        failure_reason=failure_reason,
        gaps=deduped_gaps,
        results=tuple(final_hits),
        source_results=tuple(all_attempt_results),
    )
