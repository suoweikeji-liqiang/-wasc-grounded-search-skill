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
from skill.orchestrator.query_traits import (
    ClaimType,
    ProblemStructure,
    derive_answerability_profile,
)

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]


@dataclass(frozen=True)
class ClassificationResult:
    route_label: RouteLabel
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    reason_code: str
    scores: Mapping[str, int]
    problem_structure: ProblemStructure | None = None
    claim_type: ClaimType | None = None


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
            "cybersecurity disclosure",
            "cyber risk disclosure",
            "incident disclosure",
            "item 1.05",
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
            "fedcm",
            "abnf",
            "cookie",
            "set-cookie",
            "partitioned",
            "6265bis",
            "etsi",
            "en 303 645",
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
_INDUSTRY_FILING_INTENT_MARKERS: tuple[str, ...] = (
    "annual report",
    "quarterly report",
    "10-k",
    "10q",
    "10-q",
    "20-f",
    "20f",
    "6-k",
    "6k",
    "8-k",
    "8k",
    "form 10-k",
    "form 10-q",
    "form 20-f",
    "form 6-k",
    "company filing",
)
_INDUSTRY_DISCLOSURE_INTENT_MARKERS: tuple[str, ...] = (
    "definition",
    "definitions",
    "remaining performance obligation",
    "remaining performance obligations",
    "risk factor",
    "risk factors",
    "segment",
    "revenue",
    "revenues",
    "backlog",
    "reserves",
    "transactions",
    "memberships",
    "language",
    "wording",
)
_POLICY_FILING_CROSS_DOMAIN_MARKERS: tuple[str, ...] = (
    "cybersecurity disclosure",
    "cyber risk disclosure",
    "incident disclosure",
    "item 1.05",
)
_POLICY_FILING_AUTHORITATIVE_MARKERS: tuple[str, ...] = (
    "exact",
    "timing",
    "official",
    "official text",
    "definition",
    "definitions",
    "four business days",
    "language",
)
_POLICY_FILING_ADAPTATION_MARKERS: tuple[str, ...] = (
    "impact on",
    "effect on",
    "update",
    "updates",
    "playbook",
    "rollout",
    "roadmap",
    "readiness",
)
_PARALLEL_CONJUNCTION_MARKERS: tuple[str, ...] = (
    " and ",
    " & ",
    "以及",
    "及",
    "和",
)
_INDUSTRY_PARALLEL_UPDATE_MARKERS: tuple[str, ...] = (
    "platform",
    "subscription",
    "checkout",
    "creator",
    "flow",
    "redesign",
)
_POLICY_EXPLICIT_ANCHOR_MARKERS: tuple[str, ...] = (
    "fcc",
    "ftc",
    "fda",
    "epa",
    "doj",
    "sec",
    "commission",
    "regulation",
    "directive",
    "rule",
    "rules",
    "act",
    "law",
    "dora",
    "nis2",
    "ai act",
    "cbam",
    "cyber resilience act",
    "data act",
    "ofcom",
    "nist",
    "fips",
    "cybersecurity disclosure",
    "cyber risk disclosure",
    "incident disclosure",
    "item 1.05",
)
_INDUSTRY_STANDARDS_INTENT_MARKERS: tuple[str, ...] = (
    "rfc",
    "ietf",
    "w3c",
    "webauthn",
    "fedcm",
    "6265bis",
    "partitioned",
    "http message signatures",
    "signature-input",
    "oauth",
    "chips",
    "cookie",
    "set-cookie",
    "etsi",
    "en 303 645",
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


def _has_any_marker(normalized_query: str, markers: tuple[str, ...]) -> bool:
    return any(_marker_in_query(normalized_query, marker) for marker in markers)


def _should_classify_policy_filing_mixed(normalized_query: str) -> bool:
    return _has_any_marker(
        normalized_query,
        _INDUSTRY_FILING_INTENT_MARKERS,
    ) and _has_any_marker(
        normalized_query,
        _POLICY_FILING_CROSS_DOMAIN_MARKERS,
    )


def _should_keep_policy_filing_lookup_concrete(normalized_query: str) -> bool:
    return (
        _has_any_marker(normalized_query, _INDUSTRY_FILING_INTENT_MARKERS)
        and _has_any_marker(normalized_query, _POLICY_FILING_CROSS_DOMAIN_MARKERS)
        and _has_any_marker(normalized_query, _POLICY_FILING_AUTHORITATIVE_MARKERS)
        and not _has_any_marker(normalized_query, _POLICY_FILING_ADAPTATION_MARKERS)
    )


def _should_prefer_industry_filing_lookup(normalized_query: str) -> bool:
    return (
        _has_any_marker(normalized_query, _INDUSTRY_FILING_INTENT_MARKERS)
        and _has_any_marker(normalized_query, _INDUSTRY_DISCLOSURE_INTENT_MARKERS)
        and not _has_any_marker(normalized_query, _POLICY_EXPLICIT_ANCHOR_MARKERS)
    )


def _should_prefer_industry_standards_lookup(normalized_query: str) -> bool:
    return (
        _has_any_marker(normalized_query, _INDUSTRY_STANDARDS_INTENT_MARKERS)
        and not _has_any_marker(normalized_query, _POLICY_EXPLICIT_ANCHOR_MARKERS)
    )


def _has_parallel_conjunction(normalized_query: str) -> bool:
    return any(marker in normalized_query for marker in _PARALLEL_CONJUNCTION_MARKERS)


def _should_classify_policy_industry_parallel_update_mixed(normalized_query: str) -> bool:
    return (
        _has_parallel_conjunction(normalized_query)
        and _has_any_marker(normalized_query, _POLICY_EXPLICIT_ANCHOR_MARKERS)
        and _has_any_marker(normalized_query, _INDUSTRY_PARALLEL_UPDATE_MARKERS)
    )


def _mixed_supplemental_route(
    ranked: tuple[ConcreteRoute, ...],
    scores: Mapping[str, int],
) -> ConcreteRoute | None:
    second_route = ranked[1]
    return second_route if scores[second_route] > 0 else None


def _build_classification_result(
    *,
    query: str,
    route_label: RouteLabel,
    primary_route: ConcreteRoute,
    supplemental_route: ConcreteRoute | None,
    reason_code: str,
    scores: Mapping[str, int],
) -> ClassificationResult:
    profile = derive_answerability_profile(
        query,
        route_label=route_label,
        primary_route=primary_route,
        supplemental_route=supplemental_route,
        reason_code=reason_code,
    )
    return ClassificationResult(
        route_label=route_label,
        primary_route=primary_route,
        supplemental_route=supplemental_route,
        reason_code=reason_code,
        scores=scores,
        problem_structure=profile.problem_structure,
        claim_type=profile.claim_type,
    )


def classify_query(query: str) -> ClassificationResult:
    normalized_query = normalize_query_text(query)
    tokens = query_tokens(normalized_query)
    scores = _score_routes(normalized_query)
    ranked = _rank_routes(scores)
    primary_route: ConcreteRoute = ranked[0]

    if _is_explicit_cross_domain(normalized_query, scores):
        supplemental_route: ConcreteRoute = ranked[1]
        return _build_classification_result(
            query=query,
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
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=_mixed_supplemental_route(ranked, scores),
            reason_code="short_query",
            scores=scores,
        )

    if _should_classify_policy_filing_mixed(normalized_query):
        if _should_keep_policy_filing_lookup_concrete(normalized_query):
            return _build_classification_result(
                query=query,
                route_label="policy",
                primary_route="policy",
                supplemental_route=None,
                reason_code="policy_filing_authoritative_lookup",
                scores=scores,
            )
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="policy_filing_cross_domain",
            scores=scores,
        )

    if _should_prefer_industry_filing_lookup(normalized_query):
        return _build_classification_result(
            query=query,
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_filing_override",
            scores=scores,
        )

    if _should_prefer_industry_standards_lookup(normalized_query):
        return _build_classification_result(
            query=query,
            route_label="industry",
            primary_route="industry",
            supplemental_route=None,
            reason_code="industry_standards_override",
            scores=scores,
        )

    if _should_classify_policy_industry_parallel_update_mixed(normalized_query):
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="policy_industry_parallel_update",
            scores=scores,
        )

    top_score = scores[ranked[0]]
    second_score = scores[ranked[1]]

    if top_score <= LOW_SIGNAL_SCORE_THRESHOLD:
        if top_score > 0 and second_score == 0:
            return _build_classification_result(
                query=query,
                route_label=primary_route,
                primary_route=primary_route,
                supplemental_route=None,
                reason_code=f"{primary_route}_weak_hit",
                scores=scores,
            )
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=_mixed_supplemental_route(ranked, scores),
            reason_code="low_signal",
            scores=scores,
        )

    if _is_policy_academic_research_path_ambiguity(normalized_query, ranked, scores):
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=_mixed_supplemental_route(ranked, scores),
            reason_code="policy_academic_research_path",
            scores=scores,
        )

    if top_score - second_score <= 1 and second_score > 0:
        return _build_classification_result(
            query=query,
            route_label="mixed",
            primary_route=primary_route,
            supplemental_route=_mixed_supplemental_route(ranked, scores),
            reason_code="score_tie",
            scores=scores,
        )

    return _build_classification_result(
        query=query,
        route_label=primary_route,
        primary_route=primary_route,
        supplemental_route=None,
        reason_code=f"{primary_route}_hit",
        scores=scores,
    )
