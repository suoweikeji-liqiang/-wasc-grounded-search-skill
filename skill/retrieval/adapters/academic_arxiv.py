"""arXiv adapter with deterministic scholarly fixtures."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from skill.orchestrator.normalize import normalize_query_text
from skill.retrieval.adapters.academic_live_common import (
    academic_upstream_query,
    academic_fixture_shortcut_allowed,
    rank_live_academic_records,
)
from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients import academic_api
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

_SOURCE_ID = "academic_arxiv"
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_HINTED_EUROPE_PMC_TIMEOUT_SECONDS = 0.75
_PRIMARY_API_TIMEOUT_SECONDS = 1.5
_FALLBACK_EUROPE_PMC_TIMEOUT_SECONDS = 0.5
_MIN_FIXTURE_SCORE = 6
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "Recent RAG Chunking Benchmark Paper",
        "url": "https://arxiv.org/abs/2605.11001",
        "snippet": "arXiv paper compares recent chunking strategies for retrieval-augmented generation benchmarks.",
        "arxiv_id": "2605.11001",
        "first_author": "Zhao",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Recent Benchmark Paper for Neural Retrieval Reranking",
        "url": "https://arxiv.org/abs/2605.11002",
        "snippet": "arXiv benchmark paper on cross-encoder and late-interaction retrieval reranking.",
        "arxiv_id": "2605.11002",
        "first_author": "Patel",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Recent Papers on LLM Agent Planning",
        "url": "https://arxiv.org/abs/2605.11003",
        "snippet": "arXiv paper studies planning-aware agents, tool use, and recent LLM agent planning methods.",
        "arxiv_id": "2605.11003",
        "first_author": "Kim",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Evidence normalization for retrieval grounded systems preprint",
        "url": "https://arxiv.org/abs/2604.12345",
        "snippet": "Evidence normalization benchmark preprint for retrieval.",
        "arxiv_id": "2604.12345",
        "first_author": "Lin",
        "year": 2025,
        "evidence_level": "preprint",
    },
    {
        "title": "Grounded search evidence packing preprint",
        "url": "https://arxiv.org/abs/2604.77777",
        "snippet": "Grounded search evidence packing preprint for bounded contexts.",
        "arxiv_id": "2604.77777",
        "first_author": "Chen",
        "year": 2026,
        "evidence_level": "preprint",
    },
    {
        "title": "Multi-source evidence ranking benchmark with constrained latency",
        "url": "https://arxiv.org/abs/2603.54321",
        "snippet": "Latency-aware multi-source evidence ranking benchmark preprint.",
        "arxiv_id": "2603.54321",
        "first_author": "Garcia",
        "year": 2026,
        "evidence_level": "preprint",
    },
)


def _prefers_europe_pmc(query: str) -> bool:
    return "europe pmc" in normalize_query_text(query)


def _should_probe_europe_pmc(
    *,
    prefer_europe_pmc: bool,
    ranked_records: list[dict[str, Any]],
) -> bool:
    if not prefer_europe_pmc:
        return False
    if not ranked_records:
        return False
    top_record = ranked_records[0]
    return (
        top_record.get("doi") is None
        and top_record.get("evidence_level") != "peer_reviewed"
    )


def _score(query: str, fixture: dict[str, Any]) -> int:
    return score_query_alignment(
        query,
        route="academic",
        title=str(fixture["title"]),
        snippet=str(fixture["snippet"]),
        url=str(fixture["url"]),
        year=int(fixture["year"]),
    )


async def search_fixture(query: str) -> list[RetrievalHit]:
    """Return deterministic scholarly results for offline tests."""
    ranked = sorted(
        _FIXTURES,
        key=lambda item: (_score(query, item), item["url"]),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            arxiv_id=str(item["arxiv_id"]),
            first_author=str(item["first_author"]),
            year=int(item["year"]),
            evidence_level=str(item["evidence_level"]),
        )
        for item in ranked
    ]


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live scholarly results from arXiv."""
    config = LiveRetrievalConfig.from_env()
    upstream_query = academic_upstream_query(query)
    prefer_europe_pmc = _prefers_europe_pmc(query)
    if config.fixture_shortcuts_enabled:
        fixture_hits = [
            hit
            for hit in await search_fixture(query)
            if academic_fixture_shortcut_allowed(
                query=query,
                title=hit.title,
                snippet=hit.snippet,
                url=hit.url,
                year=hit.year,
            )
        ]
        if fixture_hits:
            return fixture_hits[:3]

    try:
        records = await asyncio.wait_for(
            academic_api.search_arxiv(query=upstream_query, max_results=5),
            timeout=_PRIMARY_API_TIMEOUT_SECONDS,
        )
    except Exception:
        records = []
    ranked_records = rank_live_academic_records(
        query=query,
        records=records,
        max_results=5,
    )
    europe_pmc_records: list[dict[str, object]] = []
    if _should_probe_europe_pmc(
        prefer_europe_pmc=prefer_europe_pmc,
        ranked_records=ranked_records,
    ):
        try:
            europe_pmc_records = await asyncio.wait_for(
                academic_api.search_europe_pmc(query=upstream_query, max_results=5),
                timeout=_HINTED_EUROPE_PMC_TIMEOUT_SECONDS,
            )
        except Exception:
            europe_pmc_records = []
        if europe_pmc_records:
            ranked_records = rank_live_academic_records(
                query=query,
                records=[*records, *europe_pmc_records],
                max_results=5,
            )
    hits = [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            doi=str(item["doi"]) if item.get("doi") is not None else None,
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in ranked_records
    ]
    if hits:
        return hits

    if not europe_pmc_records:
        try:
            europe_pmc_records = await asyncio.wait_for(
                academic_api.search_europe_pmc(query=upstream_query, max_results=5),
                timeout=_FALLBACK_EUROPE_PMC_TIMEOUT_SECONDS,
            )
        except Exception:
            europe_pmc_records = []
    ranked_europe_pmc_records = rank_live_academic_records(
        query=query,
        records=europe_pmc_records,
        max_results=5,
    )
    europe_pmc_hits = [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            doi=str(item["doi"]) if item.get("doi") is not None else None,
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in ranked_europe_pmc_records
    ]
    if europe_pmc_hits:
        return europe_pmc_hits

    try:
        candidates = await search_multi_engine(
            query=f"{upstream_query} site:arxiv.org",
            engines=config.search_engines,
            max_results=5,
        )
    except Exception:
        return []

    fallback_records: list[dict[str, Any]] = []
    for candidate in candidates:
        arxiv_match = _ARXIV_ID_RE.search(candidate.url)
        if arxiv_match is None:
            continue
        arxiv_id = arxiv_match.group(1)
        year_prefix = arxiv_id[:2]
        year = 2000 + int(year_prefix) if year_prefix.isdigit() else None
        fallback_records.append(
            {
                "title": candidate.title,
                "url": candidate.url,
                "snippet": candidate.snippet,
                "arxiv_id": arxiv_id,
                "year": year,
                "evidence_level": "preprint",
            }
        )
    ranked_fallback_records = rank_live_academic_records(
        query=query,
        records=fallback_records,
        max_results=5,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            arxiv_id=str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
            first_author=str(item["first_author"]) if item.get("first_author") is not None else None,
            year=int(item["year"]) if item.get("year") is not None else None,
            evidence_level=str(item["evidence_level"]) if item.get("evidence_level") is not None else None,
        )
        for item in ranked_fallback_records
    ]


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
