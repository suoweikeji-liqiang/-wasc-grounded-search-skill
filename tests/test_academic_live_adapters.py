"""Contracts for live academic adapter implementations."""

from __future__ import annotations

import asyncio
import time

import pytest


@pytest.fixture(autouse=True)
def _disable_fixture_shortcuts(monkeypatch) -> None:
    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "0")


def test_academic_upstream_query_extracts_ascii_core_from_cjk_query() -> None:
    from skill.retrieval.adapters.academic_live_common import academic_upstream_query

    assert (
        academic_upstream_query("有哪些 grounded search evidence packing 论文")
        == "grounded search evidence packing"
    )


def test_academic_upstream_query_strips_placeholder_noise_around_ascii_terms() -> None:
    from skill.retrieval.adapters.academic_live_common import academic_upstream_query

    assert (
        academic_upstream_query("??? grounded search evidence packing ??")
        == "grounded search evidence packing"
    )


def test_asta_mcp_live_adapter_preserves_scholarly_metadata(monkeypatch) -> None:
    import skill.retrieval.adapters.academic_asta_mcp as adapter
    from skill.retrieval.live.clients import asta_mcp

    async def _fake_search_asta(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        return [
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://www.semanticscholar.org/paper/asta-123",
                "snippet": "Asta-backed scholarly paper on evidence packing.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(asta_mcp, "search_papers", _fake_search_asta)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].source_id == "academic_asta_mcp"
    assert hits[0].doi == "10.5555/evidence.2026.10"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "peer_reviewed"


def test_asta_mcp_live_adapter_ranks_and_filters_weak_upstream_results(monkeypatch) -> None:
    import skill.retrieval.adapters.academic_asta_mcp as adapter
    from skill.retrieval.live.clients import asta_mcp

    async def _fake_search_asta(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return [
            {
                "title": "General machine learning optimization paper",
                "url": "https://www.semanticscholar.org/paper/asta-generic",
                "snippet": "Generic scholarly paper on optimization.",
                "first_author": "Smith",
                "year": 2026,
                "evidence_level": "metadata_only",
            },
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://doi.org/10.5555/evidence.2026.10",
                "snippet": "Peer-reviewed paper on evidence packing.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            },
        ]

    monkeypatch.setattr(asta_mcp, "search_papers", _fake_search_asta)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing paper"))

    assert len(hits) == 1
    assert hits[0].title == "Grounded Search Evidence Packing"
    assert hits[0].doi == "10.5555/evidence.2026.10"


def test_semantic_scholar_live_adapter_preserves_scholarly_metadata(monkeypatch) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    async def _fake_search_semantic_scholar(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        return [
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://doi.org/10.5555/evidence.2026.10",
                "snippet": "Peer-reviewed paper on evidence packing.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _fake_search_semantic_scholar,
    )

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].source_id == "academic_semantic_scholar"
    assert hits[0].doi == "10.5555/evidence.2026.10"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "peer_reviewed"


def test_semantic_scholar_live_adapter_ranks_and_filters_weak_upstream_results(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    async def _fake_search_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return [
            {
                "title": "General machine learning optimization paper",
                "url": "https://www.semanticscholar.org/paper/generic-optimization",
                "snippet": "Generic peer-reviewed paper on optimization.",
                "doi": "10.5555/optimization.2026.10",
                "first_author": "Smith",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            },
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://doi.org/10.5555/evidence.2026.10",
                "snippet": "Peer-reviewed paper on evidence packing.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            },
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _fake_search_semantic_scholar,
    )

    hits = asyncio.run(adapter.search_live("grounded search evidence packing paper"))

    assert len(hits) == 1
    assert hits[0].title == "Grounded Search Evidence Packing"
    assert hits[0].doi == "10.5555/evidence.2026.10"


def test_arxiv_live_adapter_preserves_preprint_metadata(monkeypatch) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    async def _fake_search_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        return [
            {
                "title": "Grounded Search Evidence Packing Preprint",
                "url": "https://arxiv.org/abs/2604.12345",
                "snippet": "Preprint on evidence packing.",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "preprint",
            }
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _fake_search_arxiv)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].source_id == "academic_arxiv"
    assert hits[0].arxiv_id == "2604.12345"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "preprint"


def test_fixture_academic_search_remains_available_for_offline_tests() -> None:
    import skill.retrieval.adapters.academic_asta_mcp as asta_adapter
    import skill.retrieval.adapters.academic_arxiv as arxiv_adapter
    import skill.retrieval.adapters.academic_semantic_scholar as semantic_adapter

    asta_hits = asyncio.run(asta_adapter.search_fixture("evidence normalization"))
    semantic_hits = asyncio.run(semantic_adapter.search_fixture("evidence normalization"))
    arxiv_hits = asyncio.run(arxiv_adapter.search_fixture("evidence normalization"))

    assert asta_hits
    assert semantic_hits
    assert arxiv_hits
    assert any(hit.doi for hit in asta_hits)
    assert any(hit.doi for hit in semantic_hits)
    assert any(hit.arxiv_id for hit in arxiv_hits)


def test_asta_mcp_live_adapter_falls_back_to_search_discovery_when_mcp_fails(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_asta_mcp as adapter
    from skill.retrieval.live.clients import asta_mcp
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _failing_search_asta(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        raise RuntimeError("upstream overloaded")

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Grounded Search Evidence Packing",
                url="https://doi.org/10.5555/evidence.2026.10",
                snippet="Peer-reviewed paper on evidence packing.",
            )
        ]

    monkeypatch.setattr(asta_mcp, "search_papers", _failing_search_asta)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].source_id == "academic_asta_mcp"
    assert hits[0].doi == "10.5555/evidence.2026.10"
    assert hits[0].evidence_level == "peer_reviewed"


def test_arxiv_live_adapter_returns_empty_when_primary_api_is_rate_limited_and_europe_pmc_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    async def _failing_search_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        raise RuntimeError("429")

    async def _empty_europe_pmc(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        return []

    monkeypatch.setattr(academic_api, "search_arxiv", _failing_search_arxiv)
    monkeypatch.setattr(academic_api, "search_europe_pmc", _empty_europe_pmc)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert hits == []


def test_arxiv_live_adapter_returns_empty_when_no_upstream_results_match_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    async def _empty_search_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latency-aware retrieval paper"
        assert max_results == 5
        return []

    async def _empty_europe_pmc(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latency-aware retrieval paper"
        assert max_results == 5
        return []

    monkeypatch.setattr(academic_api, "search_arxiv", _empty_search_arxiv)
    monkeypatch.setattr(academic_api, "search_europe_pmc", _empty_europe_pmc)

    hits = asyncio.run(adapter.search_live("latency-aware retrieval paper"))

    assert hits == []


def test_semantic_scholar_live_adapter_returns_empty_when_primary_api_is_rate_limited_and_openalex_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    async def _failing_search_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        raise RuntimeError("429")

    async def _empty_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing"
        assert max_results == 5
        return []

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _failing_search_semantic_scholar,
    )
    monkeypatch.setattr(academic_api, "search_openalex", _empty_openalex)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert hits == []

def test_semantic_scholar_live_adapter_does_not_fallback_to_search_discovery_after_dual_empty(
    monkeypatch,
) -> None:
    import importlib
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    for module_name in tuple(sys.modules):
        if module_name == "skill" or module_name.startswith("skill."):
            sys.modules.pop(module_name)
    adapter = importlib.import_module("skill.retrieval.adapters.academic_semantic_scholar")

    async def _empty_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return []

    async def _empty_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return []

    class SearchDiscoveryCalled(BaseException):
        pass

    async def _forbidden_search_multi_engine(**_: object):
        raise SearchDiscoveryCalled("search_multi_engine should not be called")

    monkeypatch.setattr(adapter.academic_api, "search_semantic_scholar", _empty_semantic_scholar)
    monkeypatch.setattr(adapter.academic_api, "search_openalex", _empty_openalex)
    monkeypatch.setattr(adapter, "search_multi_engine", _forbidden_search_multi_engine, raising=False)

    asyncio.run(adapter.search_live("grounded search evidence packing paper"))


def test_semantic_scholar_live_adapter_falls_back_to_openalex_when_primary_api_times_out(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    observed_calls: list[str] = []

    async def _hung_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_calls.append("semantic_scholar")
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        await asyncio.sleep(0.2)
        return []

    async def _fast_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_calls.append("openalex")
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return [
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://doi.org/10.5555/evidence.2026.10",
                "snippet": "OpenAlex metadata record for the paper.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _hung_semantic_scholar,
    )
    monkeypatch.setattr(academic_api, "search_openalex", _fast_openalex)
    monkeypatch.setattr(adapter, "_PRIMARY_API_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(adapter, "_OPENALEX_TIMEOUT_SECONDS", 0.1)

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live("grounded search evidence packing paper"),
            timeout=0.25,
        )
    )

    assert sorted(observed_calls) == ["openalex", "semantic_scholar"]
    assert len(hits) == 1
    assert hits[0].doi == "10.5555/evidence.2026.10"


def test_semantic_scholar_live_adapter_prewarms_openalex_before_primary_timeout(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    observed_calls: list[str] = []

    async def _hung_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_calls.append("semantic_scholar")
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        await asyncio.sleep(0.2)
        return []

    async def _delayed_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_calls.append("openalex")
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        await asyncio.sleep(0.08)
        return [
            {
                "title": "Grounded Search Evidence Packing",
                "url": "https://doi.org/10.5555/evidence.2026.10",
                "snippet": "OpenAlex metadata record for the paper.",
                "doi": "10.5555/evidence.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _hung_semantic_scholar,
    )
    monkeypatch.setattr(academic_api, "search_openalex", _delayed_openalex)
    monkeypatch.setattr(adapter, "_PRIMARY_API_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(adapter, "_OPENALEX_TIMEOUT_SECONDS", 0.12)

    started = time.perf_counter()
    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live("grounded search evidence packing paper"),
            timeout=0.18,
        )
    )
    elapsed = time.perf_counter() - started

    assert sorted(observed_calls) == ["openalex", "semantic_scholar"]
    assert elapsed < 0.18
    assert len(hits) == 1
    assert hits[0].doi == "10.5555/evidence.2026.10"


def test_semantic_scholar_live_adapter_normalizes_mixed_language_query_for_upstreams(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    observed_queries: list[str] = []

    async def _empty_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_queries.append(query)
        return []

    async def _empty_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_queries.append(query)
        return []

    monkeypatch.setattr(academic_api, "search_semantic_scholar", _empty_semantic_scholar)
    monkeypatch.setattr(academic_api, "search_openalex", _empty_openalex)

    hits = asyncio.run(adapter.search_live("多源 evidence ranking benchmark 论文"))

    assert hits == []
    assert observed_queries == [
        "evidence ranking benchmark",
        "evidence ranking benchmark",
    ]


def test_semantic_scholar_live_adapter_accepts_slightly_slow_openalex_metadata(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    async def _empty_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        return []

    async def _slow_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        await asyncio.sleep(0.2)
        return [
            {
                "title": "Evidence Ranking Benchmark",
                "url": "https://doi.org/10.5555/evidence-ranking.2026.10",
                "snippet": "Peer-reviewed benchmark paper on evidence ranking.",
                "doi": "10.5555/evidence-ranking.2026.10",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(academic_api, "search_semantic_scholar", _empty_semantic_scholar)
    monkeypatch.setattr(academic_api, "search_openalex", _slow_openalex)

    hits = asyncio.run(adapter.search_live("evidence ranking benchmark"))

    assert len(hits) == 1
    assert hits[0].doi == "10.5555/evidence-ranking.2026.10"


def test_semantic_scholar_live_adapter_rejects_generic_fixture_shortcuts_when_live_match_is_more_specific(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "1")

    async def _empty_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "2025 retrieval-augmented generation citation grounding evaluation dataset factuality attribution"
        assert max_results == 5
        return []

    async def _fake_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "2025 retrieval-augmented generation citation grounding evaluation dataset factuality attribution"
        assert max_results == 5
        return [
            {
                "title": "Citation grounding evaluation datasets for retrieval-augmented generation",
                "url": "https://doi.org/10.5555/rag-citations.2026.10",
                "snippet": (
                    "Peer-reviewed dataset paper on factuality attribution and "
                    "citation grounding evaluation for retrieval-augmented generation."
                ),
                "doi": "10.5555/rag-citations.2026.10",
                "first_author": "Garcia",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _empty_semantic_scholar,
    )
    monkeypatch.setattr(academic_api, "search_openalex", _fake_openalex)

    hits = asyncio.run(
        adapter.search_live(
            "2025 retrieval-augmented generation citation grounding evaluation dataset factuality attribution"
        )
    )

    assert len(hits) == 1
    assert (
        hits[0].title
        == "Citation grounding evaluation datasets for retrieval-augmented generation"
    )
    assert hits[0].doi == "10.5555/rag-citations.2026.10"


def test_semantic_scholar_live_adapter_keeps_strong_fixture_shortcuts_for_known_topic_queries(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "1")

    async def _should_not_run(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        raise AssertionError(f"shortcut should handle query: {query} ({max_results})")

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _should_not_run,
    )

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert hits
    assert hits[0].title == "Grounded search evidence packing"
    assert hits[0].doi == "10.1000/grounded-search.2026.001"


def test_arxiv_live_adapter_falls_back_to_europe_pmc_when_primary_api_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    async def _empty_search_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "synthetic bone graft review paper"
        assert max_results == 5
        return []

    async def _fake_search_europe_pmc(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "synthetic bone graft review paper"
        assert max_results == 5
        return [
            {
                "title": "A Review of Synthetic Bone Grafts in Lumbar Interbody Fusion.",
                "url": "https://europepmc.org/article/MED/41899792",
                "snippet": "Review article indexed by Europe PMC.",
                "doi": "10.3390/bioengineering13030262",
                "first_author": "Wise",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _empty_search_arxiv)
    monkeypatch.setattr(academic_api, "search_europe_pmc", _fake_search_europe_pmc)

    hits = asyncio.run(adapter.search_live("synthetic bone graft review paper"))

    assert len(hits) == 1
    assert hits[0].title == "A Review of Synthetic Bone Grafts in Lumbar Interbody Fusion."
    assert hits[0].doi == "10.3390/bioengineering13030262"
    assert hits[0].first_author == "Wise"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "peer_reviewed"




def test_arxiv_live_adapter_does_not_fallback_to_search_discovery_after_dual_empty(
    monkeypatch,
) -> None:
    import importlib
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    for module_name in tuple(sys.modules):
        if module_name == "skill" or module_name.startswith("skill."):
            sys.modules.pop(module_name)
    adapter = importlib.import_module("skill.retrieval.adapters.academic_arxiv")

    async def _empty_search_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "synthetic bone graft review paper"
        assert max_results == 5
        return []

    async def _empty_search_europe_pmc(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "synthetic bone graft review paper"
        assert max_results == 5
        return []

    class SearchDiscoveryCalled(BaseException):
        pass

    async def _forbidden_search_multi_engine(**_: object) -> list[object]:
        raise SearchDiscoveryCalled("search_multi_engine should not be called")

    monkeypatch.setattr(adapter.academic_api, "search_arxiv", _empty_search_arxiv)
    monkeypatch.setattr(adapter.academic_api, "search_europe_pmc", _empty_search_europe_pmc)
    monkeypatch.setattr(adapter, "search_multi_engine", _forbidden_search_multi_engine, raising=False)

    asyncio.run(adapter.search_live("synthetic bone graft review paper"))


def test_arxiv_live_adapter_normalizes_mixed_language_query_for_upstreams(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    observed_queries: list[str] = []

    async def _empty_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_queries.append(query)
        return []

    async def _empty_europe_pmc(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        observed_queries.append(query)
        return []

    async def _empty_search_multi_engine(**kwargs: object):
        observed_queries.append(str(kwargs["query"]))
        return []

    monkeypatch.setattr(academic_api, "search_arxiv", _empty_arxiv)
    monkeypatch.setattr(academic_api, "search_europe_pmc", _empty_europe_pmc)
    monkeypatch.setattr(adapter, "search_multi_engine", _empty_search_multi_engine, raising=False)

    hits = asyncio.run(adapter.search_live("多源 evidence ranking benchmark 论文"))

    assert hits == []
    assert observed_queries == [
        "evidence ranking benchmark",
        "evidence ranking benchmark",
    ]


def test_arxiv_live_adapter_accepts_slightly_slow_primary_metadata(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    async def _slow_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        await asyncio.sleep(0.2)
        return [
            {
                "title": "Evidence Ranking Benchmark Preprint",
                "url": "https://arxiv.org/abs/2604.12345",
                "snippet": "Preprint benchmark paper on evidence ranking.",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "preprint",
            }
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _slow_arxiv)

    hits = asyncio.run(adapter.search_live("evidence ranking benchmark"))

    assert len(hits) == 1
    assert hits[0].arxiv_id == "2604.12345"


def test_arxiv_live_adapter_prefers_europe_pmc_for_explicit_repository_hint_when_match_is_stronger(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    query = (
        "2025 2026 Europe PMC single-cell foundation model transcriptomics "
        "transformer pretraining cell type annotation"
    )

    async def _fake_search_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert max_results == 5
        return [
            {
                "title": "Deep Learning in Single-Cell Analysis",
                "url": "https://arxiv.org/abs/2210.12385",
                "snippet": (
                    "Survey of single-cell analysis tasks including multimodal "
                    "integration and cell type annotation."
                ),
                "arxiv_id": "2210.12385",
                "first_author": "Yuan",
                "year": 2022,
                "evidence_level": "preprint",
            }
        ]

    async def _fake_search_europe_pmc(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert max_results == 5
        return [
            {
                "title": (
                    "Single-cell foundation model pretraining for transcriptomics "
                    "cell type annotation"
                ),
                "url": "https://europepmc.org/article/MED/42000001",
                "snippet": (
                    "Peer-reviewed study on transformer pretraining for transcriptomics "
                    "and cell type annotation in single-cell foundation models."
                ),
                "doi": "10.1038/s41592-026-00001-0",
                "first_author": "Li",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _fake_search_arxiv)
    monkeypatch.setattr(academic_api, "search_europe_pmc", _fake_search_europe_pmc)

    hits = asyncio.run(adapter.search_live(query))

    assert hits
    assert hits[0].title == (
        "Single-cell foundation model pretraining for transcriptomics "
        "cell type annotation"
    )
    assert hits[0].doi == "10.1038/s41592-026-00001-0"
    assert hits[0].evidence_level == "peer_reviewed"


def test_arxiv_live_adapter_trims_long_query_aligned_snippets_to_fit_evidence_budget(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api

    long_snippet = (
        "Sparse mixture-of-experts transformers depend on stable routing behavior under heavy load. "
        "Prior work often relies on auxiliary loss objectives that improve token balancing but can "
        "still leave collapse modes when experts receive skewed assignments during large-scale "
        "training. This paper studies auxiliary-loss-free load balancing strategy design for "
        "mixture-of-experts models, analyzes routing stability, and measures collapse mitigation "
        "under realistic throughput and optimization settings with extensive ablations across "
        "capacity factors, routing temperatures, and expert specialization drift."
    )

    async def _fake_search_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        assert query == "mixture-of-experts routing stability load balancing auxiliary loss collapse mitigation"
        assert max_results == 5
        return [
            {
                "title": "Auxiliary-Loss-Free Load Balancing Strategy for Mixture-of-Experts",
                "url": "https://arxiv.org/abs/2501.01234",
                "snippet": long_snippet,
                "arxiv_id": "2501.01234",
                "first_author": "Chen",
                "year": 2025,
                "evidence_level": "preprint",
            }
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _fake_search_arxiv)

    hits = asyncio.run(
        adapter.search_live(
            "mixture-of-experts routing stability load balancing auxiliary loss collapse mitigation"
        )
    )

    assert len(hits) == 1
    assert "mixture-of-experts" in hits[0].snippet.lower()
    assert "load balancing" in hits[0].snippet.lower()
    assert len(hits[0].snippet.split()) <= 40
