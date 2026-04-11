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
    per_source_timeout_seconds: float = PER_SOURCE_TIMEOUT_SECONDS
    overall_deadline_seconds: float = OVERALL_RETRIEVAL_DEADLINE_SECONDS
    global_concurrency_cap: int = GLOBAL_CONCURRENCY_CAP


def _build_primary_first_wave(primary_route: ConcreteRoute) -> list[PlannedSourceStep]:
    steps: list[PlannedSourceStep] = []
    for source_id in DOMAIN_FIRST_WAVE_SOURCES[primary_route]:
        if source_id in _FALLBACK_ONLY_SOURCES:
            raise ValueError(f"Fallback-only source cannot be first-wave: {source_id}")
        steps.append(
            PlannedSourceStep(
                source=RetrievalSource(source_id=source_id, route=primary_route),
            )
        )
    return steps


def _build_supplemental_first_wave(supplemental_route: ConcreteRoute) -> list[PlannedSourceStep]:
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


def _build_fallback_steps(first_wave_steps: tuple[PlannedSourceStep, ...]) -> tuple[PlannedSourceStep, ...]:
    first_wave_ids = {step.source.source_id for step in first_wave_steps}
    fallback_steps_by_key: dict[tuple[str, str], PlannedSourceStep] = {}

    for step in first_wave_steps:
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
    return tuple(fallback_steps_by_key.values())


def build_retrieval_plan(classification: ClassificationResult) -> RetrievalPlan:
    first_wave_steps: list[PlannedSourceStep] = _build_primary_first_wave(
        classification.primary_route
    )
    supplemental_route: ConcreteRoute | None = None

    if (
        classification.route_label == "mixed"
        and classification.supplemental_route is not None
    ):
        supplemental_route = classification.supplemental_route
        first_wave_steps.extend(_build_supplemental_first_wave(supplemental_route))

    first_wave = tuple(first_wave_steps)
    fallback = _build_fallback_steps(first_wave)
    return RetrievalPlan(
        route_label=classification.route_label,
        primary_route=classification.primary_route,
        supplemental_route=supplemental_route,
        first_wave_sources=first_wave,
        fallback_sources=fallback,
    )
