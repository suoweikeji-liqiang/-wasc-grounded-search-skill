"""Retrieval integration regressions for runtime orchestration and API wiring."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import RetrievalExecutionOutcome
from skill.retrieval.models import RetrievalHit


def test_execute_retrieval_pipeline_call_sequence_run_then_prioritize(monkeypatch) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            reason_code="policy_hit",
            scores={"policy": 4, "academic": 0, "industry": 0},
        )
    )
    raw_hits = [
        RetrievalHit(
            source_id="policy_official_web_allowlist_fallback",
            title="Fallback policy page",
            url="https://www.gov.cn/fallback",
            snippet="Fallback hit",
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

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "prioritize_hits", _fake_prioritize_hits)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="new policy release",
            adapter_registry={},
        )
    )

    assert events == ["run_retrieval", "prioritize_hits"]
    assert [item.source_id for item in response.results] == [
        "policy_official_registry",
        "policy_official_web_allowlist_fallback",
    ]


def test_execute_retrieval_pipeline_mixed_route_primary_dominant(monkeypatch) -> None:
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

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="policy and research synthesis",
            adapter_registry={},
        )
    )

    assert response.results
    assert response.results[0].source_id == "policy_official_registry"


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
    assert observed
