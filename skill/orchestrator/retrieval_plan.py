"""Immutable retrieval-plan contracts for first-wave and fallback sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from skill.config.retrieval import (
    DOMAIN_FIRST_WAVE_SOURCES,
    GLOBAL_CONCURRENCY_CAP,
    OVERALL_RETRIEVAL_DEADLINE_SECONDS,
    PER_SOURCE_TIMEOUT_SECONDS,
    SOURCE_BACKUP_CHAIN,
    SOURCE_CREDIBILITY_TIERS,
    SUPPLEMENTAL_STRONGEST_SOURCE,
)
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.normalize import normalize_query_text
from skill.orchestrator.query_traits import derive_query_traits
from skill.retrieval.models import RetrievalFailureReason

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]

_FALLBACK_ONLY_SOURCES: frozenset[str] = frozenset({"policy_official_web_allowlist_fallback"})
_ALLOWED_SOURCE_IDS: frozenset[str] = frozenset(
    {
        source_id
        for source_ids in DOMAIN_FIRST_WAVE_SOURCES.values()
        for source_id in source_ids
    }
    | set(SUPPLEMENTAL_STRONGEST_SOURCE.values())
    | set(SOURCE_BACKUP_CHAIN.keys())
    | {
        target
        for transitions in SOURCE_BACKUP_CHAIN.values()
        for target in transitions.values()
        if target is not None
    }
)
_PRIMARY_INDUSTRY_PER_SOURCE_TIMEOUT_SECONDS = 8.0
_PRIMARY_INDUSTRY_OVERALL_DEADLINE_SECONDS = 9.0
_PRIMARY_INDUSTRY_GLOBAL_CONCURRENCY_CAP = 3
_MIXED_OVERALL_DEADLINE_SECONDS = 8.0
_MIXED_DISCOVERY_DEADLINE_SECONDS = 2.5
_MIXED_DEEP_DEADLINE_SECONDS = 5.0
_MIXED_SHORTLIST_TOP_K = 4
_GENERALIZATION_SENSITIVE_QUERY_VARIANT_BUDGET = 5
_ACADEMIC_ARXIV_HINTS: tuple[str, ...] = ("europe pmc",)
_INDUSTRY_OFFICIAL_FIRST_MARKERS: tuple[str, ...] = (
    "10-k",
    "10k",
    "10-q",
    "10q",
    "8-k",
    "8k",
    "20-f",
    "20f",
    "6-k",
    "6k",
    "annual report",
    "quarterly report",
    "earnings",
    "filing",
    "guidance",
    "investor",
    "investors",
    "risk factors",
    "segment",
    "segments",
    "revenue",
    "revenues",
)


@dataclass(frozen=True)
class RetrievalSource:
    source_id: str
    route: ConcreteRoute
    is_supplemental: bool = False
    credibility_tier: str | None = None

    def __post_init__(self) -> None:
        if self.source_id not in _ALLOWED_SOURCE_IDS:
            raise ValueError(f"Unsupported retrieval source_id: {self.source_id}")
        if self.credibility_tier is None:
            tier = SOURCE_CREDIBILITY_TIERS.get(self.source_id)
            if tier is not None:
                object.__setattr__(self, "credibility_tier", tier)


@dataclass(frozen=True)
class PlannedSourceStep:
    source: RetrievalSource
    fallback_from_source_id: str | None = None
    trigger_on_failures: tuple[RetrievalFailureReason, ...] = ()


@dataclass(frozen=True)
class RetrievalPlan:
    route_label: RouteLabel
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    first_wave_sources: tuple[PlannedSourceStep, ...]
    fallback_sources: tuple[PlannedSourceStep, ...]
    query_variant_budget: int = 3
    per_source_timeout_seconds: float = PER_SOURCE_TIMEOUT_SECONDS
    overall_deadline_seconds: float = OVERALL_RETRIEVAL_DEADLINE_SECONDS
    global_concurrency_cap: int = GLOBAL_CONCURRENCY_CAP
    mixed_discovery_deadline_seconds: float | None = None
    mixed_deep_deadline_seconds: float | None = None
    mixed_shortlist_top_k: int = 0
    mixed_pooled_enabled: bool = False


def _industry_first_wave_source_ids(query: str | None) -> tuple[str, ...]:
    if query is None:
        return DOMAIN_FIRST_WAVE_SOURCES["industry"]
    normalized_query = normalize_query_text(query)
    if any(marker in normalized_query for marker in _INDUSTRY_OFFICIAL_FIRST_MARKERS):
        return DOMAIN_FIRST_WAVE_SOURCES["industry"]
    if derive_query_traits(query).has_trend_intent:
        return ("industry_web_discovery",)
    return (
        "industry_web_discovery",
        "industry_news_rss",
        "industry_official_or_filings",
    )


def _build_primary_first_wave(
    primary_route: ConcreteRoute,
    *,
    query: str | None = None,
) -> list[PlannedSourceStep]:
    steps: list[PlannedSourceStep] = []
    source_ids = (
        _industry_first_wave_source_ids(query)
        if primary_route == "industry"
        else DOMAIN_FIRST_WAVE_SOURCES[primary_route]
    )
    for source_id in source_ids:
        if source_id in _FALLBACK_ONLY_SOURCES:
            raise ValueError(f"Fallback-only source cannot be first-wave: {source_id}")
        steps.append(
            PlannedSourceStep(
                source=RetrievalSource(source_id=source_id, route=primary_route),
            )
        )
    return steps


def _build_supplemental_first_wave(
    supplemental_route: ConcreteRoute,
    *,
    query: str | None = None,
) -> list[PlannedSourceStep]:
    if supplemental_route == "industry":
        return [
            PlannedSourceStep(
                source=RetrievalSource(
                    source_id=source_id,
                    route=supplemental_route,
                    is_supplemental=True,
                ),
            )
            for source_id in _industry_first_wave_source_ids(query)
            if source_id not in _FALLBACK_ONLY_SOURCES
        ]
    supplemental_source_id = SUPPLEMENTAL_STRONGEST_SOURCE[supplemental_route]
    if supplemental_source_id in _FALLBACK_ONLY_SOURCES:
        raise ValueError(
            f"Fallback-only source cannot be supplemental first-wave: {supplemental_source_id}"
        )
    return [
        PlannedSourceStep(
            source=RetrievalSource(
                source_id=supplemental_source_id,
                route=supplemental_route,
                is_supplemental=True,
            ),
        )
    ]


def _build_primary_academic_parallel_plan(
    *,
    query: str | None,
) -> tuple[PlannedSourceStep, ...]:
    ordered_source_ids = [
        "academic_semantic_scholar",
        "academic_arxiv",
    ]
    if query is not None and _prefer_arxiv_first_for_academic_query(query):
        ordered_source_ids = [
            "academic_arxiv",
            "academic_semantic_scholar",
        ]

    return tuple(
        PlannedSourceStep(
            source=RetrievalSource(
                source_id=source_id,
                route="academic",
            )
        )
        for source_id in ordered_source_ids
    )


def _prefer_arxiv_first_for_academic_query(query: str) -> bool:
    normalized_query = normalize_query_text(query)
    return any(hint in normalized_query for hint in _ACADEMIC_ARXIV_HINTS)


def _build_fallback_steps(first_wave_steps: tuple[PlannedSourceStep, ...]) -> tuple[PlannedSourceStep, ...]:
    first_wave_ids = {step.source.source_id for step in first_wave_steps}
    fallback_steps_by_key: dict[tuple[str, str], PlannedSourceStep] = {}
    pending_steps = list(first_wave_steps)
    processed_steps: set[tuple[str, str | None, str, bool]] = set()

    while pending_steps:
        step = pending_steps.pop(0)
        step_key = (
            step.source.source_id,
            step.fallback_from_source_id,
            step.source.route,
            step.source.is_supplemental,
        )
        if step_key in processed_steps:
            continue
        processed_steps.add(step_key)
        transitions = SOURCE_BACKUP_CHAIN.get(step.source.source_id, {})
        for failure_reason, target_source_id in transitions.items():
            if target_source_id is None or target_source_id in first_wave_ids:
                continue

            dedupe_key = (step.source.source_id, target_source_id)
            existing_step = fallback_steps_by_key.get(dedupe_key)
            if existing_step is None:
                fallback_steps_by_key[dedupe_key] = PlannedSourceStep(
                    source=RetrievalSource(
                        source_id=target_source_id,
                        route=step.source.route,
                        is_supplemental=step.source.is_supplemental,
                    ),
                    fallback_from_source_id=step.source.source_id,
                    trigger_on_failures=(failure_reason,),  # type: ignore[arg-type]
                )
                continue

            if failure_reason not in existing_step.trigger_on_failures:
                fallback_steps_by_key[dedupe_key] = PlannedSourceStep(
                    source=existing_step.source,
                    fallback_from_source_id=existing_step.fallback_from_source_id,
                    trigger_on_failures=(
                        *existing_step.trigger_on_failures,
                        failure_reason,
                    ),
                )
                existing_step = fallback_steps_by_key[dedupe_key]
            pending_steps.append(fallback_steps_by_key[dedupe_key])
    return tuple(fallback_steps_by_key.values())


def build_retrieval_plan(
    classification: ClassificationResult,
    *,
    query: str | None = None,
) -> RetrievalPlan:
    supplemental_route: ConcreteRoute | None = None
    fallback: tuple[PlannedSourceStep, ...] | None = None

    if classification.route_label == "academic" and classification.primary_route == "academic":
        first_wave_steps = list(_build_primary_academic_parallel_plan(query=query))
    else:
        first_wave_steps = _build_primary_first_wave(
            classification.primary_route,
            query=query,
        )

    if (
        classification.route_label == "mixed"
        and classification.supplemental_route is not None
    ):
        supplemental_route = classification.supplemental_route
        first_wave_steps.extend(
            _build_supplemental_first_wave(
                supplemental_route,
                query=query,
            )
        )

    first_wave = tuple(first_wave_steps)
    if fallback is None:
        fallback = _build_fallback_steps(first_wave)
    per_source_timeout_seconds = PER_SOURCE_TIMEOUT_SECONDS
    overall_deadline_seconds = OVERALL_RETRIEVAL_DEADLINE_SECONDS
    query_variant_budget = 3
    global_concurrency_cap = GLOBAL_CONCURRENCY_CAP
    if classification.route_label == "industry" and classification.primary_route == "industry":
        per_source_timeout_seconds = _PRIMARY_INDUSTRY_PER_SOURCE_TIMEOUT_SECONDS
        overall_deadline_seconds = _PRIMARY_INDUSTRY_OVERALL_DEADLINE_SECONDS
        query_variant_budget = _GENERALIZATION_SENSITIVE_QUERY_VARIANT_BUDGET
        global_concurrency_cap = _PRIMARY_INDUSTRY_GLOBAL_CONCURRENCY_CAP
    elif classification.route_label == "mixed":
        overall_deadline_seconds = _MIXED_OVERALL_DEADLINE_SECONDS
        query_variant_budget = _GENERALIZATION_SENSITIVE_QUERY_VARIANT_BUDGET
    return RetrievalPlan(
        route_label=classification.route_label,
        primary_route=classification.primary_route,
        supplemental_route=supplemental_route,
        first_wave_sources=first_wave,
        fallback_sources=fallback,
        query_variant_budget=query_variant_budget,
        per_source_timeout_seconds=per_source_timeout_seconds,
        overall_deadline_seconds=overall_deadline_seconds,
        global_concurrency_cap=global_concurrency_cap,
        mixed_discovery_deadline_seconds=(
            _MIXED_DISCOVERY_DEADLINE_SECONDS
            if classification.route_label == "mixed"
            else None
        ),
        mixed_deep_deadline_seconds=(
            _MIXED_DEEP_DEADLINE_SECONDS
            if classification.route_label == "mixed"
            else None
        ),
        mixed_shortlist_top_k=(
            _MIXED_SHORTLIST_TOP_K if classification.route_label == "mixed" else 0
        ),
        mixed_pooled_enabled=(
            classification.route_label == "mixed" and supplemental_route is not None
        ),
    )
