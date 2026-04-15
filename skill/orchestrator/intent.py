"""Rule-first deterministic intent classifier for Phase 1 routing."""

from __future__ import annotations

import re
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

_ENGLISH_MARKER_TABLE: Mapping[ConcreteRoute, tuple[str, ...]] = MappingProxyType(
    {
        "policy": (
            "fda",
            "fcc",
            "etsi",
            "cyber trust mark",
            "policy",
            "regulation",
            "reglement",
            "directive",
            "directives",
            "rule",
            "rules",
            "registry",
            "guidance",
            "guide",
            "guia",
            "deadline",
            "deadlines",
            "compliance",
            "obligation",
            "obligations",
            "transposition",
            "official text",
            "effective date",
            "order",
            "act",
            "ai act",
            "law",
            "fips",
            "nist",
            "exemption",
            "revision",
            "amendment",
            "cgmp",
            "inspection classification",
            "oai",
            "vai",
            "nai",
            "pccp",
            "predetermined change control plan",
            "officiel",
            "oficial",
            "export controls",
            "climate",
            "methane",
            "emissions",
        ),
        "academic": (
            "paper",
            "research",
            "study",
            "survey",
            "review",
            "dataset",
            "evaluation",
            "factuality",
            "attribution",
            "hallucination",
            "distillation",
            "pretraining",
            "pre-training",
            "post-training",
            "post training",
            "finetuning",
            "fine-tuning",
            "rlhf",
            "dpo",
            "ipo",
            "kto",
            "preference optimization",
            "watermarking",
            "transformer",
            "diffusion",
            "single-cell",
            "transcriptomics",
            "lora",
            "planning",
            "agent planning",
            "retrieval",
            "grounded",
            "evidence packing",
            "evidence",
            "normalization",
            "chunking",
        ),
        "industry": (
            "industry",
            "market",
            "share",
            "forecast",
            "outlook",
            "trend",
            "shipment",
            "shipments",
            "sales",
            "capacity",
            "battery",
            "recycling",
            "semiconductor",
            "packaging",
            "earnings",
            "annual report",
            "filing",
            "form 10-k",
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
            "guidance",
            "capex",
            "supply chain",
            "risk factors",
            "revenue",
            "segment",
            "backlog",
            "liquidity",
            "warranty",
            "reserves",
            "cet1",
            "rpk",
            "demand",
            "rfc",
            "ietf",
            "w3c",
            "oauth",
            "webauthn",
            "abnf",
            "cookie",
            "set-cookie",
            "spec",
            "specification",
            "gpu",
            "server",
        ),
    }
)

_ENGLISH_EXPLICIT_CROSS_DOMAIN_MARKERS: tuple[str, ...] = (
    "impact on",
    "effect on",
    "impact of",
    "effect of",
)
_POLICY_ACADEMIC_RESEARCH_PATH_MARKERS: tuple[str, ...] = (
    "\u7814\u7a76\u8def\u5f84",
    "\u7814\u7a76\u6846\u67b6",
)

_PRECEDENCE_INDEX: Mapping[str, int] = MappingProxyType(
    {route: index for index, route in enumerate(ROUTE_PRECEDENCE)}
)


def _marker_in_query(normalized_query: str, marker: str) -> bool:
    if marker.isascii():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
            normalized_query,
        ) is not None
    return marker in normalized_query


def _score_routes(normalized_query: str) -> Mapping[str, int]:
    scored = {
        route: sum(2 for marker in markers if _marker_in_query(normalized_query, marker))
        + sum(
            2
            for marker in _ENGLISH_MARKER_TABLE[route]
            if _marker_in_query(normalized_query, marker)
        )
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
        _marker_in_query(normalized_query, marker)
        for marker in (
            *EXPLICIT_CROSS_DOMAIN_MARKERS,
            *_ENGLISH_EXPLICIT_CROSS_DOMAIN_MARKERS,
        )
    )
    active_domain_count = sum(1 for score in scores.values() if score > 0)
    return has_cross_domain_phrase and active_domain_count >= 2


def _is_policy_academic_research_path_ambiguity(
    normalized_query: str,
    ranked: tuple[ConcreteRoute, ...],
    scores: Mapping[str, int],
) -> bool:
    return (
        ranked[0] == "policy"
        and ranked[1] == "academic"
        and scores["policy"] > 0
        and scores["academic"] > 0
        and any(marker in normalized_query for marker in _POLICY_ACADEMIC_RESEARCH_PATH_MARKERS)
    )


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
        if top_score > 0 and second_score == 0:
            return ClassificationResult(
                route_label=primary_route,
                primary_route=primary_route,
                supplemental_route=None,
                reason_code=f"{primary_route}_weak_hit",
                scores=scores,
            )
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=None,
            reason_code="low_signal",
            scores=scores,
        )

    if _is_policy_academic_research_path_ambiguity(normalized_query, ranked, scores):
        return ClassificationResult(
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=None,
            reason_code="policy_academic_research_path",
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
