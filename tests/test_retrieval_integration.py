"""Retrieval integration regressions for runtime orchestration and API wiring."""

from __future__ import annotations

import asyncio
import pytest

from fastapi.testclient import TestClient

from skill.evidence.models import EvidencePack
from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import RetrievalExecutionOutcome
from skill.retrieval.models import RetrievalHit


def test_execute_retrieval_pipeline_runs_post_priority_evidence_pipeline_in_order(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="academic",
            reason_code="explicit_cross_domain",
            scores={"policy": 5, "academic": 4, "industry": 0},
        )
    )
    raw_hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Supplemental paper",
            url="https://www.semanticscholar.org/paper/abc",
            snippet="Supplemental academic evidence",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Official registry page",
            url="https://www.mee.gov.cn/official",
            snippet="Official hit",
        ),
    ]
    events: list[str] = []

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        events.append("run_retrieval")
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(raw_hits),
            source_results=(),
        )

    def _fake_prioritize_hits(**kwargs: object) -> list[RetrievalHit]:
        events.append("prioritize_hits")
        assert kwargs["hits"] == raw_hits
        return [raw_hits[1], raw_hits[0]]

    def _fake_normalize_hit_candidates(**kwargs: object) -> list[str]:
        events.append("normalize_hit_candidates")
        assert kwargs["hits"] == [raw_hits[1], raw_hits[0]]
        assert kwargs["route_role_by_source"] == {
            "academic_semantic_scholar": "supplemental"
        }
        return ["normalized"]

    def _fake_collapse_evidence_records(records: list[str]) -> list[str]:
        events.append("collapse_evidence_records")
        assert records == ["normalized"]
        return ["canonical"]

    def _fake_score_evidence_records(records: list[str]) -> list[str]:
        events.append("score_evidence_records")
        assert records == ["canonical"]
        return ["scored"]

    def _fake_build_evidence_pack(
        records: list[str],
        *,
        token_budget: int,
        top_k: int,
        supplemental_min_items: int,
    ) -> EvidencePack:
        events.append("build_evidence_pack")
        assert records == ["scored"]
        assert token_budget > 0
        assert top_k > 0
        assert supplemental_min_items == 1
        return EvidencePack(
            raw_records=(),
            canonical_evidence=(),
            clipped=True,
            pruned=True,
            total_token_estimate=0,
        )

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "prioritize_hits", _fake_prioritize_hits)
    monkeypatch.setattr(orchestrate, "normalize_hit_candidates", _fake_normalize_hit_candidates)
    monkeypatch.setattr(orchestrate, "collapse_evidence_records", _fake_collapse_evidence_records)
    monkeypatch.setattr(orchestrate, "score_evidence_records", _fake_score_evidence_records)
    monkeypatch.setattr(orchestrate, "build_evidence_pack", _fake_build_evidence_pack)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="new policy release",
            adapter_registry={},
        )
    )

    assert events == [
        "run_retrieval",
        "prioritize_hits",
        "normalize_hit_candidates",
        "collapse_evidence_records",
        "score_evidence_records",
        "build_evidence_pack",
    ]
    assert [item.source_id for item in response.results] == [
        "policy_official_registry",
        "academic_semantic_scholar",
    ]
    assert response.evidence_clipped is True


def test_execute_retrieval_pipeline_mixed_route_preserves_primary_results_and_clip_flag(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="academic",
            reason_code="explicit_cross_domain",
            scores={"policy": 5, "academic": 4, "industry": 0},
        )
    )
    raw_hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Academic evidence",
            url="https://www.semanticscholar.org/paper/xyz",
            snippet="Supplemental source",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Policy official evidence",
            url="https://www.gov.cn/zhengce/official",
            snippet="Primary-route source",
        ),
    ]

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(raw_hits),
            source_results=(),
        )

    def _fake_normalize_hit_candidates(**kwargs: object) -> list[object]:
        assert kwargs["route_role_by_source"] == {
            "academic_semantic_scholar": "supplemental"
        }
        return []

    def _fake_build_evidence_pack(
        records: list[object],
        *,
        token_budget: int,
        top_k: int,
        supplemental_min_items: int,
    ) -> EvidencePack:
        assert records == []
        assert token_budget > 0
        assert top_k > 0
        assert supplemental_min_items == 1
        return EvidencePack(
            raw_records=(),
            canonical_evidence=(),
            clipped=False,
            pruned=False,
            total_token_estimate=0,
        )

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "normalize_hit_candidates", _fake_normalize_hit_candidates)
    monkeypatch.setattr(orchestrate, "collapse_evidence_records", lambda records: [])
    monkeypatch.setattr(orchestrate, "score_evidence_records", lambda records: [])
    monkeypatch.setattr(orchestrate, "build_evidence_pack", _fake_build_evidence_pack)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="policy and research synthesis",
            adapter_registry={},
        )
    )

    assert response.results
    assert response.results[0].source_id == "policy_official_registry"
    assert response.evidence_clipped is False


def test_retrieve_api_endpoint_routes_through_execute_retrieval_pipeline(monkeypatch) -> None:
    import skill.api.entry as api_entry

    observed: list[tuple[str, str | None]] = []

    async def _fake_pipeline(**kwargs: object) -> RetrieveResponse:
        plan = kwargs["plan"]
        observed.append((plan.primary_route, plan.supplemental_route))
        return RetrieveResponse(
            route_label=plan.route_label,
            primary_route=plan.primary_route,
            supplemental_route=plan.supplemental_route,
            browser_automation="disabled",
            status="success",
            failure_reason=None,
            gaps=[],
            evidence_clipped=True,
            results=[
                RetrieveResultItem(
                    source_id="policy_official_registry",
                    title="Official result",
                    url="https://www.gov.cn/official",
                    snippet="Grounded evidence",
                    credibility_tier="official_government",
                )
            ],
        )

    monkeypatch.setattr(
        api_entry,
        "execute_retrieval_pipeline",
        _fake_pipeline,
        raising=False,
    )

    client = TestClient(api_entry.app)
    response = client.post("/retrieve", json={"query": "latest policy bulletin"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["results"][0]["source_id"] == "policy_official_registry"
    assert payload["evidence_clipped"] is True
    assert "total_token_estimate" not in payload
    assert "token_budget" not in payload
    assert observed


def test_retrieve_response_enforces_outcome_invariants() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        RetrieveResponse(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            status="success",
            failure_reason="timeout",
            gaps=[],
            evidence_clipped=False,
            results=[],
        )

    with pytest.raises(ValueError, match="gaps"):
        RetrieveResponse(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            status="failure_gaps",
            failure_reason=None,
            gaps=[],
            evidence_clipped=False,
            results=[],
        )


def test_policy_adapters_emit_observed_authority_and_date_metadata() -> None:
    from skill.retrieval.adapters.policy_official_registry import search as registry_search
    from skill.retrieval.adapters.policy_official_web_allowlist import (
        search as allowlist_search,
    )

    registry_hits = asyncio.run(registry_search("official policy bulletin"))
    allowlist_hits = asyncio.run(allowlist_search("official policy bulletin"))
    combined_hits = [*registry_hits, *allowlist_hits]

    assert combined_hits
    assert all(
        getattr(hit, "authority", None)
        and (
            getattr(hit, "publication_date", None)
            or getattr(hit, "effective_date", None)
        )
        for hit in combined_hits
    )
    assert any(getattr(hit, "version", None) for hit in combined_hits)
    assert any(getattr(hit, "jurisdiction", None) for hit in combined_hits)


def test_academic_adapters_emit_observed_identifier_metadata() -> None:
    from skill.retrieval.adapters.academic_arxiv import search as arxiv_search
    from skill.retrieval.adapters.academic_semantic_scholar import (
        search as semantic_search,
    )

    semantic_hits = asyncio.run(semantic_search("evidence normalization"))
    arxiv_hits = asyncio.run(arxiv_search("evidence normalization"))

    assert semantic_hits
    assert arxiv_hits
    assert any(
        getattr(hit, "doi", None)
        and getattr(hit, "first_author", None)
        and getattr(hit, "year", None)
        and getattr(hit, "evidence_level", None)
        for hit in semantic_hits
    )
    assert any(
        getattr(hit, "arxiv_id", None)
        and getattr(hit, "first_author", None)
        and getattr(hit, "year", None)
        and getattr(hit, "evidence_level", None)
        for hit in arxiv_hits
    )


def test_normalize_hits_preserves_observed_metadata_from_mapping_payloads() -> None:
    from skill.retrieval.engine import _normalize_hits

    hits = _normalize_hits(
        raw_hits=[
            {
                "title": "Observed policy bulletin",
                "url": "https://www.gov.cn/zhengce/observed-bulletin",
                "snippet": "Observed metadata fixture",
                "authority": "State Council",
                "jurisdiction": "CN",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "doi": "10.1000/example-doi",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ],
        source_id="policy_official_registry",
    )

    assert hits[0].authority == "State Council"
    assert hits[0].jurisdiction == "CN"
    assert hits[0].publication_date == "2026-04-01"
    assert hits[0].effective_date == "2026-05-01"
    assert hits[0].version == "2026-04 edition"
    assert hits[0].doi == "10.1000/example-doi"
    assert hits[0].arxiv_id == "2604.12345"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "peer_reviewed"
