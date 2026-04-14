"""Immutable retrieval-planning constants for Phase 2."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Mapping

ConcreteRoute = Literal["policy", "industry", "academic"]

PER_SOURCE_TIMEOUT_SECONDS: Final[float] = 3.0
OVERALL_RETRIEVAL_DEADLINE_SECONDS: Final[float] = 6.0
GLOBAL_CONCURRENCY_CAP: Final[int] = 6

DOMAIN_FIRST_WAVE_SOURCES: Final[Mapping[ConcreteRoute, tuple[str, ...]]] = MappingProxyType(
    {
        "policy": ("policy_official_registry",),
        "academic": (
            "academic_asta_mcp",
            "academic_semantic_scholar",
            "academic_arxiv",
        ),
        "industry": ("industry_ddgs",),
    }
)

SUPPLEMENTAL_STRONGEST_SOURCE: Final[Mapping[ConcreteRoute, str]] = MappingProxyType(
    {
        "policy": "policy_official_registry",
        "academic": "academic_semantic_scholar",
        "industry": "industry_ddgs",
    }
)

SOURCE_BACKUP_CHAIN: Final[Mapping[str, Mapping[str, str | None]]] = MappingProxyType(
    {
        "policy_official_registry": MappingProxyType(
            {
                "no_hits": "policy_official_web_allowlist_fallback",
                "timeout": "policy_official_web_allowlist_fallback",
                "rate_limited": "policy_official_web_allowlist_fallback",
            }
        ),
        "policy_official_web_allowlist_fallback": MappingProxyType(
            {
                "no_hits": None,
                "timeout": None,
                "rate_limited": None,
            }
        ),
        "academic_asta_mcp": MappingProxyType(
            {
                "no_hits": None,
                "timeout": None,
                "rate_limited": None,
            }
        ),
        "academic_semantic_scholar": MappingProxyType(
            {
                "no_hits": "academic_asta_mcp",
                "timeout": "academic_asta_mcp",
                "rate_limited": "academic_asta_mcp",
            }
        ),
        "academic_arxiv": MappingProxyType(
            {
                "no_hits": None,
                "timeout": None,
                "rate_limited": None,
            }
        ),
        "industry_ddgs": MappingProxyType(
            {
                "no_hits": None,
                "timeout": None,
                "rate_limited": None,
            }
        ),
    }
)

SOURCE_CREDIBILITY_TIERS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "policy_official_registry": "official_government",
        "policy_official_web_allowlist_fallback": "regulator",
        "academic_asta_mcp": "citation_index",
        "academic_semantic_scholar": "academic_metadata",
        "academic_arxiv": "paper_repository",
        "industry_ddgs": "trusted_news",
    }
)
