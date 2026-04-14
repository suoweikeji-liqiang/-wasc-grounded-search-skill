"""Competition-oriented query trait extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from skill.config.routes import ACADEMIC_MARKERS, INDUSTRY_MARKERS, POLICY_MARKERS
from skill.orchestrator.normalize import normalize_query_text

_YEAR_RE = re.compile(r"(?<!\d)20\d{2}(?!\d)")

_POLICY_CHANGE_MARKERS: tuple[str, ...] = (
    "\u4fee\u8ba2",
    "\u4fee\u6b63",
    "\u53d8\u5316",
    "\u8c03\u6574",
    "\u65b0\u589e",
    "\u66f4\u65b0",
    "revision",
    "amendment",
    "update",
)
_VERSION_INTENT_MARKERS: tuple[str, ...] = (
    "\u7248\u672c",
    "\u4fee\u8ba2",
    "\u4fee\u6b63",
    "\u53d8\u5316",
    "\u66f4\u65b0",
    "version",
    "latest",
    "revision",
    "amendment",
)
_EFFECTIVE_DATE_MARKERS: tuple[str, ...] = (
    "\u751f\u6548",
    "\u65bd\u884c",
    "\u5b9e\u65bd",
    "\u65f6\u95f4",
    "\u65e5\u671f",
    "effective date",
)
_TREND_MARKERS: tuple[str, ...] = (
    "\u8d8b\u52bf",
    "\u9884\u6d4b",
    "\u4efd\u989d",
    "\u51fa\u8d27",
    "\u9500\u91cf",
    "\u5e02\u573a",
    "trend",
    "forecast",
    "outlook",
    "share",
    "shipment",
    "shipments",
    "sales",
)
_CROSS_DOMAIN_MARKERS: tuple[str, ...] = (
    "\u5f71\u54cd",
    "\u6548\u5e94",
    "\u6bd4\u8f83",
    "\u5bf9\u6bd4",
    "\u4ea4\u53c9",
    "\u7ed3\u5408",
    "\u8054\u52a8",
    "\u5bf9\u884c\u4e1a",
    "\u653f\u7b56\u5bf9\u884c\u4e1a",
    "\u5bf9\u7814\u7a76",
    "\u7814\u7a76\u4e0e\u76d1\u7ba1",
    "\u4ea7\u4e1a\u843d\u5730",
    "vs",
    "impact on",
    "effect on",
    "impact of",
    "effect of",
)
_ROUTE_ENGLISH_MARKERS: dict[str, tuple[str, ...]] = {
    "policy": (
        "policy",
        "regulation",
        "directive",
        "directives",
        "rule",
        "rules",
        "registry",
        "guidance",
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
        "export controls",
        "controls",
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
        "finetuning",
        "fine-tuning",
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


@dataclass(frozen=True)
class QueryTraits:
    has_year: bool
    has_version_intent: bool
    has_effective_date_intent: bool
    has_trend_intent: bool
    is_policy_change: bool
    is_cross_domain_impact: bool


def _marker_in_text(text: str, marker: str) -> bool:
    if marker.isascii():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
            text,
        ) is not None
    return marker in text


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(_marker_in_text(text, marker) for marker in markers)


def _route_signal_count(text: str) -> int:
    route_markers = {
        "policy": POLICY_MARKERS,
        "academic": ACADEMIC_MARKERS,
        "industry": INDUSTRY_MARKERS,
    }
    active_routes = 0
    for route, markers in route_markers.items():
        if _contains_any(text, markers) or _contains_any(text, _ROUTE_ENGLISH_MARKERS[route]):
            active_routes += 1
    return active_routes


def derive_query_traits(query: str) -> QueryTraits:
    normalized = normalize_query_text(query)
    is_cross_domain_impact = _contains_any(normalized, _CROSS_DOMAIN_MARKERS) or (
        "\u4e0e" in normalized and _route_signal_count(normalized) >= 2
    )
    return QueryTraits(
        has_year=bool(_YEAR_RE.search(normalized)),
        has_version_intent=_contains_any(normalized, _VERSION_INTENT_MARKERS),
        has_effective_date_intent=_contains_any(normalized, _EFFECTIVE_DATE_MARKERS),
        has_trend_intent=_contains_any(normalized, _TREND_MARKERS),
        is_policy_change=_contains_any(normalized, _POLICY_CHANGE_MARKERS),
        is_cross_domain_impact=is_cross_domain_impact,
    )
