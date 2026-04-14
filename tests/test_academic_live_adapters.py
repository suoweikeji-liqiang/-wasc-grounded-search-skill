"""Contracts for live academic adapter implementations."""

from __future__ import annotations

import asyncio


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
    import skill.retrieval.adapters.academic_arxiv as arxiv_adapter
    import skill.retrieval.adapters.academic_semantic_scholar as semantic_adapter

    semantic_hits = asyncio.run(semantic_adapter.search_fixture("evidence normalization"))
    arxiv_hits = asyncio.run(arxiv_adapter.search_fixture("evidence normalization"))

    assert semantic_hits
    assert arxiv_hits
    assert any(hit.doi for hit in semantic_hits)
    assert any(hit.arxiv_id for hit in arxiv_hits)


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
