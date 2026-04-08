"""Rule-first deterministic intent classifier for Phase 1 routing."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from skill.config.routes import (
    ACADEMIC_MARKERS,
    EXPLICIT_CROSS_DOMAIN_MARKERS,
    INDUSTRY_MARKERS,
    LOW_SIGNAL_SCORE_THRESHOLD,
    POLICY_MARKERS,
    ROUTE_PRECEDENCE,
    SHORT_QUERY_CHAR_THRESHOLD,
    SHORT_QUERY_TOKEN_THRESHOLD,
)
from skill.orchestrator.normalize import normalize_query_text, query_tokens

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]


@dataclass(frozen=True)
class ClassificationResult:
    route_label: RouteLabel
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    reason_code: str
    scores: Mapping[str, int]


_MARKER_TABLE: Mapping[ConcreteRoute, tuple[str, ...]] = MappingProxyType(
    {
        "policy": POLICY_MARKERS,
        "academic": ACADEMIC_MARKERS,
        "industry": INDUSTRY_MARKERS,
    }
)

_PRECEDENCE_INDEX: Mapping[str, int] = MappingProxyType(
    {route: index for index, route in enumerate(ROUTE_PRECEDENCE)}
)


def _score_routes(normalized_query: str) -> Mapping[str, int]:
    scored = {
        route: sum(2 for marker in markers if marker in normalized_query)
        for route, markers in _MARKER_TABLE.items()
    }
    return MappingProxyType(scored)


def _rank_routes(scores: Mapping[str, int]) -> tuple[ConcreteRoute, ...]:
    ranked = sorted(
        ("policy", "academic", "industry"),
        key=lambda route: (-scores[route], _PRECEDENCE_INDEX[route]),
    )
    return tuple(ranked)


def _is_explicit_cross_domain(normalized_query: str, scores: Mapping[str, int]) -> bool:
    has_cross_domain_phrase = any(
        marker in normalized_query for marker in EXPLICIT_CROSS_DOMAIN_MARKERS
    )
    active_domain_count = sum(1 for score in scores.values() if score > 0)
    return has_cross_domain_phrase and active_domain_count >= 2


def classify_query(query: str) -> ClassificationResult:
    normalized_query = normalize_query_text(query)
    tokens = query_tokens(normalized_query)
    scores = _score_routes(normalized_query)
    ranked = _rank_routes(scores)
    primary_route: ConcreteRoute = ranked[0]

    if _is_explicit_cross_domain(normalized_query, scores):
        supplemental_route: ConcreteRoute = ranked[1]
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=supplemental_route,
            reason_code="explicit_cross_domain",
            scores=scores,
        )

    is_short_query = (
        len(normalized_query.replace(" ", "")) < SHORT_QUERY_CHAR_THRESHOLD
        or len(tokens) < SHORT_QUERY_TOKEN_THRESHOLD
    )
    if is_short_query:
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=None,
            reason_code="short_query",
            scores=scores,
        )

    top_score = scores[ranked[0]]
    second_score = scores[ranked[1]]

    if top_score <= LOW_SIGNAL_SCORE_THRESHOLD:
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=None,
            reason_code="low_signal",
            scores=scores,
        )

    if top_score - second_score <= 1 and second_score > 0:
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=None,
            reason_code="score_tie",
            scores=scores,
        )

    return ClassificationResult(
        route_label=primary_route,
        primary_route=primary_route,
        supplemental_route=None,
        reason_code=f"{primary_route}_hit",
        scores=scores,
    )
