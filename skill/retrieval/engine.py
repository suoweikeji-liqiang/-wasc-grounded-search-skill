"""Runtime retrieval execution with first-wave concurrency and hard budgets."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from skill.orchestrator.retrieval_plan import PlannedSourceStep, RetrievalPlan
from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.retrieval.fallback_fsm import (
    map_exception_to_failure_reason,
)
from skill.retrieval.models import (
    RetrievalFailureReason,
    RetrievalHit,
    RetrievalStatus,
    SourceExecutionResult,
)
from skill.retrieval.priority import score_query_alignment
from skill.retrieval.query_variants import QueryVariant, build_query_variants

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]
_LEGACY_INDUSTRY_ADAPTER_FALLBACKS: frozenset[str] = frozenset(
    {
        "industry_official_or_filings",
        "industry_web_discovery",
        "industry_news_rss",
    }
)
_ACADEMIC_VARIANT_PRIORITY: dict[str, int] = {
    "academic_source_hint": 0,
    "academic_ascii_core": 1,
    "academic_topic_focus": 2,
    "academic_phrase_locked": 3,
    "original": 4,
    "academic_evidence_type_focus": 5,
    "academic_lookup": 6,
    "academic_benchmark": 7,
    "academic_focus": 8,
}
_INDUSTRY_VARIANT_PRIORITY: dict[str, int] = {
    "original": 0,
    "industry_cjk_gloss": 1,
    "document_focus": 2,
    "document_concept_focus": 3,
    "core_focus": 4,
    "industry_focus": 5,
    "industry_trend": 6,
    "industry_share": 7,
}
_ACADEMIC_QUALITY_GATE_SOURCE_ID = "academic_semantic_scholar"
_ACADEMIC_ASTA_FALLBACK_TIMEOUT_SECONDS = 1.0
_ACADEMIC_MIN_STRONG_TITLE_FOCUS_OVERLAP = 2
_ACADEMIC_MIN_STRONG_ALIGNMENT_SCORE = 12
_ACADEMIC_FOCUS_STOPWORDS: frozenset[str] = frozenset(
    {
        "academic",
        "arxiv",
        "benchmark",
        "benchmarks",
        "europe",
        "model",
        "models",
        "openalex",
        "paper",
        "papers",
        "pmc",
        "recent",
        "research",
        "review",
        "scholar",
        "semantic",
        "studies",
        "study",
        "survey",
    }
)
_INDUSTRY_EARLY_STOP_MARKERS: tuple[str, ...] = (
    "advanced packaging",
    "packaging capacity",
    "semiconductor packaging",
    "cowos",
)
_INDUSTRY_GLOSS_VARIANT_TIMEOUT_RATIO = 0.5
_MIXED_STRUCTURAL_REASON_BONUS: dict[str, int] = {
    "cross_domain_fragment_focus": 6,
    "document_focus": 4,
    "document_concept_focus": 4,
    "core_focus": 3,
    "academic_phrase_locked": 3,
    "academic_topic_focus": 3,
    "academic_evidence_type_focus": 2,
    "academic_source_hint": 1,
    "original": 0,
}


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
    deduped_by_key: dict[tuple[str, str, str], RetrievalHit] = {}
    for hit in hits:
        key = _retrieval_hit_key(hit)
        existing = deduped_by_key.get(key)
        if existing is None:
            deduped_by_key[key] = hit
            continue
        deduped_by_key[key] = _merge_hit_provenance(existing, hit)
    return tuple(deduped_by_key.values())


def _retrieval_hit_key(hit: RetrievalHit) -> tuple[str, str, str]:
    return (
        hit.source_id,
        hit.url.strip().lower(),
        hit.title.strip().lower(),
    )


def _merge_variant_pairs(
    *,
    existing_reasons: tuple[str, ...],
    existing_queries: tuple[str, ...],
    new_reasons: tuple[str, ...],
    new_queries: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    merged_pairs: list[tuple[str, str]] = []
    for reason_code, variant_query in zip(existing_reasons, existing_queries, strict=False):
        pair = (reason_code, variant_query)
        if pair not in merged_pairs:
            merged_pairs.append(pair)
    for reason_code, variant_query in zip(new_reasons, new_queries, strict=False):
        pair = (reason_code, variant_query)
        if pair not in merged_pairs:
            merged_pairs.append(pair)
    return (
        tuple(pair[0] for pair in merged_pairs),
        tuple(pair[1] for pair in merged_pairs),
    )


def _merge_hit_provenance(existing: RetrievalHit, candidate: RetrievalHit) -> RetrievalHit:
    merged_reason_codes, merged_queries = _merge_variant_pairs(
        existing_reasons=existing.variant_reason_codes,
        existing_queries=existing.variant_queries,
        new_reasons=candidate.variant_reason_codes,
        new_queries=candidate.variant_queries,
    )
    return replace(
        existing,
        target_route=existing.target_route or candidate.target_route,
        variant_reason_codes=merged_reason_codes,
        variant_queries=merged_queries,
    )


def _annotate_hit_provenance(
    hit: RetrievalHit,
    *,
    target_route: str,
    variant: QueryVariant,
) -> RetrievalHit:
    merged_reason_codes, merged_queries = _merge_variant_pairs(
        existing_reasons=hit.variant_reason_codes,
        existing_queries=hit.variant_queries,
        new_reasons=(variant.reason_code,),
        new_queries=(variant.query,),
    )
    return replace(
        hit,
        target_route=target_route,
        variant_reason_codes=merged_reason_codes,
        variant_queries=merged_queries,
    )


def _mixed_variant_pairs(query: str, hit: RetrievalHit) -> tuple[tuple[str, str], ...]:
    pairs = tuple(
        (reason_code, variant_query)
        for reason_code, variant_query in zip(
            hit.variant_reason_codes,
            hit.variant_queries,
            strict=False,
        )
        if variant_query
    )
    if pairs:
        return pairs
    return (("original", query),)


def _mixed_hit_score(
    *,
    query: str,
    route: str,
    hit: RetrievalHit,
) -> tuple[int, int, int]:
    best_score = (-1, -1, -1)
    for reason_code, variant_query in _mixed_variant_pairs(query, hit):
        alignment = score_query_alignment(
            variant_query,
            route=route,  # type: ignore[arg-type]
            title=hit.title,
            snippet=hit.snippet,
            url=hit.url,
            authority=hit.authority,
            publication_date=hit.publication_date,
            effective_date=hit.effective_date,
            version=hit.version,
            year=hit.year,
        )
        structural_bonus = _MIXED_STRUCTURAL_REASON_BONUS.get(
            reason_code,
            1 if reason_code != "original" else 0,
        )
        candidate_score = (
            alignment + structural_bonus,
            1 if reason_code != "original" else 0,
            alignment,
        )
        if candidate_score > best_score:
            best_score = candidate_score
    return best_score


def _rank_mixed_hits_for_route(
    *,
    query: str,
    route: str,
    hits: list[RetrievalHit],
) -> list[tuple[tuple[int, int, int], RetrievalHit]]:
    deduped_hits = list(_dedupe_hits(hits))
    scored_hits = [
        (
            _mixed_hit_score(
                query=query,
                route=route,
                hit=hit,
            ),
            index,
            hit,
        )
        for index, hit in enumerate(deduped_hits)
    ]
    scored_hits.sort(
        key=lambda item: (
            -item[0][0],
            -item[0][1],
            -item[0][2],
            -len(item[2].title),
            -len(item[2].snippet),
            item[1],
        )
    )
    return [(score, hit) for score, _, hit in scored_hits]


def _shortlist_mixed_hits(
    *,
    query: str,
    primary_route: str,
    supplemental_route: str,
    primary_hits: list[RetrievalHit],
    supplemental_hits: list[RetrievalHit],
    top_k: int,
) -> tuple[RetrievalHit, ...]:
    ranked_primary = _rank_mixed_hits_for_route(
        query=query,
        route=primary_route,
        hits=primary_hits,
    )
    ranked_supplemental = _rank_mixed_hits_for_route(
        query=query,
        route=supplemental_route,
        hits=supplemental_hits,
    )
    if not ranked_primary or not ranked_supplemental:
        return ()

    effective_top_k = max(2, top_k)
    shortlist: list[RetrievalHit] = []
    seen: set[tuple[str, str, str]] = set()

    def _append_hit(hit: RetrievalHit) -> None:
        key = _retrieval_hit_key(hit)
        if key in seen:
            return
        seen.add(key)
        shortlist.append(hit)

    _append_hit(ranked_primary[0][1])
    _append_hit(ranked_supplemental[0][1])

    remaining = ranked_primary[1:] + ranked_supplemental[1:]
    remaining.sort(
        key=lambda item: (
            -item[0][0],
            -item[0][1],
            -item[0][2],
            -len(item[1].title),
            -len(item[1].snippet),
        )
    )
    for _, hit in remaining:
        if len(shortlist) >= effective_top_k:
            break
        _append_hit(hit)

    return tuple(shortlist[:effective_top_k])


def _mixed_top_hit_is_viable(score: tuple[int, int, int]) -> bool:
    total_score, focused_match, alignment = score
    return focused_match > 0 or alignment >= 6 or total_score >= 8


def _academic_focus_terms(text: str) -> set[str]:
    normalized = normalize_query_text(text)
    return {
        token
        for token in query_tokens(normalized)
        if (
            not token.isdigit()
            and (
                (token.isascii() and len(token) >= 8 and token not in _ACADEMIC_FOCUS_STOPWORDS)
                or (not token.isascii())
            )
        )
    }


def _academic_hit_is_strong_for_query(
    *,
    query: str,
    focus_terms: set[str],
    hit: RetrievalHit,
) -> bool:
    title_overlap = len(focus_terms & _academic_focus_terms(hit.title))
    if title_overlap >= _ACADEMIC_MIN_STRONG_TITLE_FOCUS_OVERLAP:
        return True

    if title_overlap == 0:
        return False

    alignment = score_query_alignment(
        query,
        route="academic",
        title=hit.title,
        snippet=hit.snippet,
        url=hit.url,
        authority=hit.authority,
        publication_date=hit.publication_date,
        effective_date=hit.effective_date,
        version=hit.version,
        year=hit.year,
    )
    return (
        alignment >= _ACADEMIC_MIN_STRONG_ALIGNMENT_SCORE
        and hit.evidence_level != "metadata_only"
    )


def _academic_success_requires_fallback(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
    result: SourceExecutionResult,
) -> bool:
    if result.status != "success" or not result.hits:
        return False
    if plan.route_label != "academic" or plan.primary_route != "academic":
        return False
    if step.source.source_id != _ACADEMIC_QUALITY_GATE_SOURCE_ID:
        return False

    focus_terms = _academic_focus_terms(query)
    if len(focus_terms) < _ACADEMIC_MIN_STRONG_TITLE_FOCUS_OVERLAP:
        return False

    return not any(
        _academic_hit_is_strong_for_query(
            query=query,
            focus_terms=focus_terms,
            hit=hit,
        )
        for hit in result.hits
    )


def _skip_academic_asta_fallback(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    current_source: str,
    fallback_step: PlannedSourceStep,
    first_wave_results: Mapping[str, SourceExecutionResult],
) -> bool:
    if fallback_step.source.source_id != "academic_asta_mcp":
        return False

    if (
        plan.route_label == "mixed"
        and step.source.is_supplemental
        and any(
            result.status == "success" and result.hits
            for source_id, result in first_wave_results.items()
            if source_id != current_source
        )
    ):
        return True

    if plan.route_label != "academic" or plan.primary_route != "academic":
        return False

    other_metadata_results = tuple(
        result
        for source_id, result in first_wave_results.items()
        if source_id != current_source
        and source_id in {"academic_semantic_scholar", "academic_arxiv"}
    )
    return any(
        result.status == "success" and bool(result.hits)
        for result in other_metadata_results
    )

    for source_id in ("academic_semantic_scholar", "academic_arxiv"):
        if source_id == current_source:
            continue
        result = first_wave_results.get(source_id)
        if result is not None and result.status == "success" and result.hits:
            return True
    return False


def _stop_after_first_success(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
) -> bool:
    if step.source.route == "academic":
        return True

    normalized_query = normalize_query_text(query)
    return (
        plan.route_label == "industry"
        and plan.primary_route == "industry"
        and step.source.source_id == "industry_web_discovery"
        and step.source.route == "industry"
        and not step.source.is_supplemental
        and any(marker in normalized_query for marker in _INDUSTRY_EARLY_STOP_MARKERS)
    )


def _stop_after_first_no_hits(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
) -> bool:
    normalized_query = normalize_query_text(query)
    return (
        plan.route_label == "industry"
        and plan.primary_route == "industry"
        and step.source.route == "industry"
        and not step.source.is_supplemental
        and step.source.source_id
        in {
            "industry_web_discovery",
            "industry_news_rss",
            "industry_official_or_filings",
        }
        and any(marker in normalized_query for marker in _INDUSTRY_EARLY_STOP_MARKERS)
    )


def _fallback_timeout_seconds(
    *,
    fallback_step: PlannedSourceStep,
    plan: RetrievalPlan,
    remaining: float,
) -> float:
    timeout_seconds = min(plan.per_source_timeout_seconds, remaining)
    if fallback_step.source.source_id == "academic_asta_mcp":
        return min(timeout_seconds, _ACADEMIC_ASTA_FALLBACK_TIMEOUT_SECONDS)
    return timeout_seconds


def _should_stop_first_wave_early(
    *,
    plan: RetrievalPlan,
    query: str,
    completed_results: Mapping[str, SourceExecutionResult],
) -> bool:
    normalized_query = normalize_query_text(query)
    if (
        plan.route_label != "industry"
        or plan.primary_route != "industry"
        or not any(marker in normalized_query for marker in _INDUSTRY_EARLY_STOP_MARKERS)
    ):
        return False

    web_discovery_result = completed_results.get("industry_web_discovery")
    return (
        web_discovery_result is not None
        and web_discovery_result.status == "success"
        and bool(web_discovery_result.hits)
    )


def _stage_for_step(step: PlannedSourceStep) -> str:
    return "fallback" if step.fallback_from_source_id is not None else "first_wave"


def _elapsed_ms(started_at: float, finished_at: float) -> int:
    return int(round(max(0.0, finished_at - started_at) * 1000))


def _started_at_ms(retrieval_started_at: float, source_started_at: float) -> int:
    return int(round(max(0.0, source_started_at - retrieval_started_at) * 1000))


def _status_code_from_exception(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    return int(status_code) if isinstance(status_code, int) else None


def _error_class_from_exception(exc: BaseException) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    status_code = _status_code_from_exception(exc)
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and 500 <= status_code < 600:
        return "http_5xx"
    return "adapter_error"


def _default_error_class(result: SourceExecutionResult) -> str:
    if result.status == "success":
        return "ok"
    if result.failure_reason == "timeout":
        return "timeout"
    if result.failure_reason == "rate_limited":
        return "rate_limited"
    if result.failure_reason == "no_hits":
        return "parse_empty"
    return "adapter_error"


def _with_source_telemetry(
    result: SourceExecutionResult,
    *,
    stage: str,
    retrieval_started_at: float,
    source_started_at: float,
    source_finished_at: float,
    error_class: str | None = None,
    was_cancelled_by_deadline: bool = False,
) -> SourceExecutionResult:
    return replace(
        result,
        stage=stage,
        started_at_ms=_started_at_ms(retrieval_started_at, source_started_at),
        elapsed_ms=_elapsed_ms(source_started_at, source_finished_at),
        error_class=error_class or _default_error_class(result),
        was_cancelled_by_deadline=was_cancelled_by_deadline,
    )


async def _run_single_source(
    source_id: str,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    timeout_seconds: float,
) -> SourceExecutionResult:
    adapter = adapter_registry.get(source_id)
    if adapter is None and source_id in _LEGACY_INDUSTRY_ADAPTER_FALLBACKS:
        adapter = adapter_registry.get("industry_ddgs")
    if adapter is None:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(source_id,),
            error_class="adapter_error",
        )

    if timeout_seconds <= 0:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="timeout",
            gaps=(source_id,),
            error_class="timeout",
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
            error_class=_error_class_from_exception(exc),
        )

    if not raw_hits:
        return SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="no_hits",
            gaps=(source_id,),
            error_class="parse_empty",
        )

    hits = _normalize_hits(raw_hits=raw_hits, source_id=source_id)
    return SourceExecutionResult(
        source_id=source_id,
        status="success",
        hits=hits,
        error_class="ok",
    )


async def _run_source_variants(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    deadline_at: float,
    retrieval_started_at: float,
) -> SourceExecutionResult:
    source_id = step.source.source_id
    stage = _stage_for_step(step)
    variants = build_query_variants(
        query=query,
        route_label=plan.route_label,
        primary_route=plan.primary_route,
        supplemental_route=plan.supplemental_route,
        target_route=step.source.route,
        variant_limit=plan.query_variant_budget,
    )
    if step.source.route == "academic":
        variants = _prioritize_academic_variants(variants)
    elif step.source.route == "industry":
        variants = _prioritize_industry_variants(variants)

    loop = asyncio.get_running_loop()
    source_started_at = loop.time()
    merged_hits: list[RetrievalHit] = []
    last_failure_reason: RetrievalFailureReason = "no_hits"
    last_error_class = "parse_empty"

    for variant in variants:
        remaining = deadline_at - loop.time()
        if remaining <= 0:
            break

        attempt = await _run_single_source(
            source_id=source_id,
            query=variant.query,
            adapter_registry=adapter_registry,
            timeout_seconds=_variant_timeout_seconds(
                step=step,
                plan=plan,
                variant=variant,
                variants=variants,
                remaining=remaining,
            ),
        )
        if attempt.status == "success":
            merged_hits.extend(
                _annotate_hit_provenance(
                    hit,
                    target_route=step.source.route,
                    variant=variant,
                )
                for hit in attempt.hits
            )
            if _stop_after_first_success(step=step, plan=plan, query=query):
                return _with_source_telemetry(
                    SourceExecutionResult(
                        source_id=source_id,
                        status="success",
                        hits=_dedupe_hits(merged_hits),
                        error_class="ok",
                    ),
                    stage=stage,
                    retrieval_started_at=retrieval_started_at,
                    source_started_at=source_started_at,
                    source_finished_at=loop.time(),
                )
            continue

        failure_reason = attempt.failure_reason or "adapter_error"
        if failure_reason == "no_hits":
            last_failure_reason = failure_reason
            last_error_class = attempt.error_class
            if _stop_after_first_no_hits(
                step=step,
                plan=plan,
                query=query,
            ):
                break
            continue
        last_failure_reason = failure_reason
        last_error_class = attempt.error_class
        if _should_continue_after_variant_failure(
            step=step,
            plan=plan,
            variant=variant,
            variants=variants,
            failure_reason=failure_reason,
            remaining=deadline_at - loop.time(),
        ):
            continue

        if merged_hits:
            return _with_source_telemetry(
                SourceExecutionResult(
                    source_id=source_id,
                    status="success",
                    hits=_dedupe_hits(merged_hits),
                    error_class="ok",
                ),
                stage=stage,
                retrieval_started_at=retrieval_started_at,
                source_started_at=source_started_at,
                source_finished_at=loop.time(),
            )

        return _with_source_telemetry(
            attempt,
            stage=stage,
            retrieval_started_at=retrieval_started_at,
            source_started_at=source_started_at,
            source_finished_at=loop.time(),
            error_class=attempt.error_class,
        )

    if merged_hits:
        return _with_source_telemetry(
            SourceExecutionResult(
                source_id=source_id,
                status="success",
                hits=_dedupe_hits(merged_hits),
                error_class="ok",
            ),
            stage=stage,
            retrieval_started_at=retrieval_started_at,
            source_started_at=source_started_at,
            source_finished_at=loop.time(),
        )

    if loop.time() >= deadline_at:
        last_failure_reason = "timeout"
        last_error_class = "timeout"

    return _with_source_telemetry(
        SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason=last_failure_reason,
            gaps=(source_id,),
            error_class=last_error_class,
        ),
        stage=stage,
        retrieval_started_at=retrieval_started_at,
        source_started_at=source_started_at,
        source_finished_at=loop.time(),
        error_class=last_error_class,
    )


def _prioritize_academic_variants(
    variants: tuple[QueryVariant, ...],
) -> tuple[QueryVariant, ...]:
    if len(variants) <= 1:
        return variants
    if not any(
        variant.reason_code
        in {
            "academic_source_hint",
            "academic_ascii_core",
            "academic_phrase_locked",
            "academic_evidence_type_focus",
            "academic_topic_focus",
        }
        for variant in variants
    ):
        return variants
    indexed_variants = list(enumerate(variants))
    indexed_variants.sort(
        key=lambda pair: (
            _ACADEMIC_VARIANT_PRIORITY.get(pair[1].reason_code, 99),
            pair[0],
        )
    )
    return tuple(variant for _, variant in indexed_variants)


def _prioritize_industry_variants(
    variants: tuple[QueryVariant, ...],
) -> tuple[QueryVariant, ...]:
    if len(variants) <= 1:
        return variants
    if not any(
        variant.reason_code == "industry_cjk_gloss"
        for variant in variants
    ):
        return variants
    indexed_variants = list(enumerate(variants))
    indexed_variants.sort(
        key=lambda pair: (
            _INDUSTRY_VARIANT_PRIORITY.get(pair[1].reason_code, 99),
            pair[0],
        )
    )
    return tuple(variant for _, variant in indexed_variants)


def _variant_timeout_seconds(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    variant: QueryVariant,
    variants: tuple[QueryVariant, ...],
    remaining: float,
) -> float:
    timeout_seconds = remaining
    if (
        len(variants) > 1
        and plan.route_label == "industry"
        and plan.primary_route == "industry"
        and step.source.route == "industry"
        and not step.source.is_supplemental
        and variant.reason_code == "industry_cjk_gloss"
    ):
        timeout_seconds = min(
            timeout_seconds,
            max(0.0, plan.per_source_timeout_seconds * _INDUSTRY_GLOSS_VARIANT_TIMEOUT_RATIO),
        )
    return timeout_seconds


def _should_continue_after_variant_failure(
    *,
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    variant: QueryVariant,
    variants: tuple[QueryVariant, ...],
    failure_reason: RetrievalFailureReason,
    remaining: float,
) -> bool:
    return (
        remaining > 0
        and len(variants) > 1
        and failure_reason == "timeout"
        and plan.route_label == "industry"
        and plan.primary_route == "industry"
        and step.source.route == "industry"
        and not step.source.is_supplemental
        and variant.reason_code == "industry_cjk_gloss"
    )


async def _run_source_step(
    step: PlannedSourceStep,
    plan: RetrievalPlan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    timeout_seconds: float,
    retrieval_started_at: float,
    semaphore: asyncio.Semaphore | None = None,
) -> SourceExecutionResult:
    loop = asyncio.get_running_loop()
    deadline_at = loop.time() + max(0.0, timeout_seconds)
    source_started_at = loop.time()
    stage = _stage_for_step(step)
    if semaphore is None:
        return await _run_source_variants(
            step=step,
            plan=plan,
            query=query,
            adapter_registry=adapter_registry,
            deadline_at=deadline_at,
            retrieval_started_at=retrieval_started_at,
        )

    remaining = deadline_at - loop.time()
    if remaining <= 0:
        return _with_source_telemetry(
            SourceExecutionResult(
                source_id=step.source.source_id,
                status="failure_gaps",
                failure_reason="timeout",
                gaps=(step.source.source_id,),
                error_class="timeout",
            ),
            stage=stage,
            retrieval_started_at=retrieval_started_at,
            source_started_at=source_started_at,
            source_finished_at=loop.time(),
            error_class="timeout",
        )
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=remaining)
    except asyncio.TimeoutError:
        return _with_source_telemetry(
            SourceExecutionResult(
                source_id=step.source.source_id,
                status="failure_gaps",
                failure_reason="timeout",
                gaps=(step.source.source_id,),
                error_class="timeout",
            ),
            stage=stage,
            retrieval_started_at=retrieval_started_at,
            source_started_at=source_started_at,
            source_finished_at=loop.time(),
            error_class="timeout",
        )
    try:
        return await _run_source_variants(
            step=step,
            plan=plan,
            query=query,
            adapter_registry=adapter_registry,
            deadline_at=deadline_at,
            retrieval_started_at=retrieval_started_at,
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
    retrieval_started_at: float,
) -> dict[str, SourceExecutionResult]:
    semaphore = asyncio.Semaphore(max(1, concurrency_cap))
    tasks: dict[asyncio.Task[SourceExecutionResult], tuple[str, float]] = {}
    loop = asyncio.get_running_loop()
    deadline_at = loop.time() + max(0.0, overall_timeout_seconds)

    for step in first_wave_steps:
        source_id = step.source.source_id
        task_started_at = loop.time()
        task = asyncio.create_task(
            _run_source_step(
                step=step,
                plan=plan,
                query=query,
                adapter_registry=adapter_registry,
                timeout_seconds=per_source_timeout_seconds,
                retrieval_started_at=retrieval_started_at,
                semaphore=semaphore,
            )
        )
        tasks[task] = (source_id, task_started_at)

    by_source: dict[str, SourceExecutionResult] = {}
    stopped_early = False

    while tasks:
        remaining = deadline_at - loop.time()
        if remaining <= 0:
            break

        done, _ = await asyncio.wait(
            tuple(tasks.keys()),
            timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            break

        for done_task in done:
            source_id, task_started_at = tasks.pop(done_task)
            try:
                by_source[source_id] = done_task.result()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                by_source[source_id] = _with_source_telemetry(
                    SourceExecutionResult(
                        source_id=source_id,
                        status="failure_gaps",
                        failure_reason=map_exception_to_failure_reason(exc),
                        gaps=(source_id,),
                        error_class=_error_class_from_exception(exc),
                    ),
                    stage="first_wave",
                    retrieval_started_at=retrieval_started_at,
                    source_started_at=task_started_at,
                    source_finished_at=loop.time(),
                    error_class=_error_class_from_exception(exc),
                )

        if _should_stop_first_wave_early(
            plan=plan,
            query=query,
            completed_results=by_source,
        ):
            stopped_early = True
            break

    if tasks:
        for pending_task in tasks:
            if not pending_task.done():
                pending_task.cancel()
        await asyncio.gather(*tasks.keys(), return_exceptions=True)

    for pending_task, (source_id, task_started_at) in tasks.items():
        by_source[source_id] = _with_source_telemetry(
            SourceExecutionResult(
                source_id=source_id,
                status="failure_gaps",
                failure_reason="timeout",
                gaps=(source_id,),
                error_class="timeout",
            ),
            stage="first_wave",
            retrieval_started_at=retrieval_started_at,
            source_started_at=task_started_at,
            source_finished_at=loop.time(),
            error_class="timeout",
            was_cancelled_by_deadline=not stopped_early,
        )

    return by_source


async def _run_mixed_pooled_path(
    *,
    plan: RetrievalPlan,
    query: str,
    first_wave_steps: tuple[PlannedSourceStep, ...],
    first_wave_results: Mapping[str, SourceExecutionResult],
    adapter_registry: Mapping[str, Adapter],
    deadline_at: float,
) -> RetrievalExecutionOutcome | None:
    del adapter_registry, deadline_at
    supplemental_route = plan.supplemental_route
    if supplemental_route is None or plan.mixed_shortlist_top_k <= 0:
        return None

    ordered_source_results: list[SourceExecutionResult] = []
    primary_hits: list[RetrievalHit] = []
    supplemental_hits: list[RetrievalHit] = []
    unresolved_reasons: list[RetrievalFailureReason] = []
    unresolved_gaps: list[str] = []

    for step in first_wave_steps:
        source_id = step.source.source_id
        result = first_wave_results.get(source_id) or SourceExecutionResult(
            source_id=source_id,
            status="failure_gaps",
            failure_reason="adapter_error",
            gaps=(source_id,),
        )
        ordered_source_results.append(result)

        if result.status == "success":
            if step.source.route == plan.primary_route and not step.source.is_supplemental:
                primary_hits.extend(result.hits)
            elif step.source.route == supplemental_route:
                supplemental_hits.extend(result.hits)
            continue

        unresolved_reasons.append(result.failure_reason or "adapter_error")
        unresolved_gaps.extend(result.gaps)

    ranked_primary = _rank_mixed_hits_for_route(
        query=query,
        route=plan.primary_route,
        hits=primary_hits,
    )
    ranked_supplemental = _rank_mixed_hits_for_route(
        query=query,
        route=supplemental_route,
        hits=supplemental_hits,
    )
    if not ranked_primary or not ranked_supplemental:
        return None
    if not (
        _mixed_top_hit_is_viable(ranked_primary[0][0])
        and _mixed_top_hit_is_viable(ranked_supplemental[0][0])
    ):
        return None

    shortlist = _shortlist_mixed_hits(
        query=query,
        primary_route=plan.primary_route,
        supplemental_route=supplemental_route,
        primary_hits=primary_hits,
        supplemental_hits=supplemental_hits,
        top_k=plan.mixed_shortlist_top_k,
    )
    if not shortlist:
        return None

    deduped_gaps = tuple(dict.fromkeys(unresolved_gaps))
    status: RetrievalStatus = "success" if not unresolved_reasons else "partial"
    failure_reason = None if not unresolved_reasons else unresolved_reasons[0]
    return RetrievalExecutionOutcome(
        status=status,
        failure_reason=failure_reason,
        gaps=deduped_gaps,
        results=shortlist,
        source_results=tuple(ordered_source_results),
    )


async def _run_standard_retrieval_path(
    *,
    plan: RetrievalPlan,
    query: str,
    first_wave_steps: tuple[PlannedSourceStep, ...],
    first_wave_results: Mapping[str, SourceExecutionResult],
    adapter_registry: Mapping[str, Adapter],
    deadline_at: float,
    retrieval_started_at: float,
) -> RetrievalExecutionOutcome:
    loop = asyncio.get_running_loop()
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

        provisional_hits: list[RetrievalHit] = []
        if primary_result.status == "success":
            if not _academic_success_requires_fallback(
                step=step,
                plan=plan,
                query=query,
                result=primary_result,
            ):
                final_hits.extend(primary_result.hits)
                continue
            provisional_hits.extend(primary_result.hits)
            chain_gaps: list[str] = []
            failure_reason: RetrievalFailureReason = "no_hits"
        else:
            chain_gaps = list(primary_result.gaps)
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
            if _skip_academic_asta_fallback(
                step=step,
                plan=plan,
                current_source=current_source,
                fallback_step=fallback_step,
                first_wave_results=first_wave_results,
            ):
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
                timeout_seconds=_fallback_timeout_seconds(
                    fallback_step=fallback_step,
                    plan=plan,
                    remaining=remaining,
                ),
                retrieval_started_at=retrieval_started_at,
            )
            all_attempt_results.append(fallback_result)

            if fallback_result.status == "success":
                final_hits.extend(provisional_hits)
                final_hits.extend(fallback_result.hits)
                recovered = True
                break

            chain_gaps.extend(fallback_result.gaps)
            failure_reason = fallback_result.failure_reason or "adapter_error"
            current_source = fallback_source_id

        if not recovered:
            final_hits.extend(provisional_hits)
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
    retrieval_started_at = loop.time()
    deadline_at = retrieval_started_at + max(0.0, plan.overall_deadline_seconds)
    first_wave_timeout_seconds = max(0.0, deadline_at - loop.time())
    if plan.route_label == "mixed" and plan.mixed_discovery_deadline_seconds is not None:
        first_wave_timeout_seconds = min(
            first_wave_timeout_seconds,
            max(0.0, plan.mixed_discovery_deadline_seconds),
        )
    first_wave_results = await _run_first_wave(
        plan=plan,
        first_wave_steps=first_wave_steps,
        query=query,
        adapter_registry=adapter_registry,
        per_source_timeout_seconds=max(0.0, plan.per_source_timeout_seconds),
        overall_timeout_seconds=first_wave_timeout_seconds,
        concurrency_cap=plan.global_concurrency_cap,
        retrieval_started_at=retrieval_started_at,
    )
    if (
        plan.route_label == "mixed"
        and plan.supplemental_route is not None
        and plan.mixed_pooled_enabled
    ):
        pooled_outcome = await _run_mixed_pooled_path(
            plan=plan,
            query=query,
            first_wave_steps=first_wave_steps,
            first_wave_results=first_wave_results,
            adapter_registry=adapter_registry,
            deadline_at=deadline_at,
        )
        if pooled_outcome is not None:
            return pooled_outcome
    return await _run_standard_retrieval_path(
        plan=plan,
        query=query,
        first_wave_steps=first_wave_steps,
        first_wave_results=first_wave_results,
        adapter_registry=adapter_registry,
        deadline_at=deadline_at,
        retrieval_started_at=retrieval_started_at,
    )
