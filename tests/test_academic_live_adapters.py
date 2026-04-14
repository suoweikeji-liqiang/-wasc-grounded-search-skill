"""Contracts for live academic adapter implementations."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _disable_fixture_shortcuts(monkeypatch) -> None:
    monkeypatch.setenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", "0")


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


def test_arxiv_live_adapter_falls_back_to_search_discovery_when_api_is_rate_limited(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _failing_search_arxiv(*, query: str, max_results: int = 5) -> list[dict[str, object]]:
        raise RuntimeError("429")

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Grounded Search Evidence Packing Preprint",
                url="https://arxiv.org/abs/2604.12345",
                snippet="Preprint on evidence packing.",
            )
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _failing_search_arxiv)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].arxiv_id == "2604.12345"
    assert hits[0].evidence_level == "preprint"


def test_arxiv_live_adapter_filters_weak_search_discovery_fallback_hits(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_arxiv as adapter
    from skill.retrieval.live.clients import academic_api
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _empty_search_arxiv(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "latency-aware retrieval paper"
        assert max_results == 5
        return []

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Unrelated distributed systems paper",
                url="https://arxiv.org/abs/2601.00001",
                snippet="A paper on distributed systems.",
            )
        ]

    monkeypatch.setattr(academic_api, "search_arxiv", _empty_search_arxiv)
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)

    hits = asyncio.run(adapter.search_live("latency-aware retrieval paper"))

    assert hits == []


def test_semantic_scholar_live_adapter_falls_back_to_search_discovery_when_api_is_rate_limited(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api
    from skill.retrieval.live.clients.search_discovery import SearchCandidate

    async def _failing_search_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        raise RuntimeError("429")

    async def _fake_search_multi_engine(**_: object) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                engine="bing",
                title="Grounded Search Evidence Packing",
                url="https://doi.org/10.5555/evidence.2026.10",
                snippet="Peer-reviewed paper on evidence packing.",
            )
        ]

    monkeypatch.setattr(
        academic_api,
        "search_semantic_scholar",
        _failing_search_semantic_scholar,
    )
    monkeypatch.setattr(adapter, "search_multi_engine", _fake_search_multi_engine)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing"))

    assert len(hits) == 1
    assert hits[0].doi == "10.5555/evidence.2026.10"
    assert hits[0].evidence_level == "peer_reviewed"


def test_semantic_scholar_live_adapter_falls_back_to_openalex_when_primary_api_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.academic_semantic_scholar as adapter
    from skill.retrieval.live.clients import academic_api

    async def _empty_semantic_scholar(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "grounded search evidence packing paper"
        assert max_results == 5
        return []

    async def _fake_openalex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
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
        _empty_semantic_scholar,
    )
    monkeypatch.setattr(academic_api, "search_openalex", _fake_openalex)

    hits = asyncio.run(adapter.search_live("grounded search evidence packing paper"))

    assert len(hits) == 1
    assert hits[0].title == "Grounded Search Evidence Packing"
    assert hits[0].doi == "10.5555/evidence.2026.10"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026


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
