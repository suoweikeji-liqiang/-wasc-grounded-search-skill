from __future__ import annotations

import asyncio
from dataclasses import replace

from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.models import RetrievalHit, SourceExecutionResult


def _hit(*, source_id: str, title: str) -> RetrievalHit:
    return RetrievalHit(
        source_id=source_id,
        title=title,
        url=f"https://example.com/{title}",
        snippet=f"{title} snippet",
    )


def test_run_retrieval_uses_mixed_discovery_budget_and_pooled_hook(monkeypatch) -> None:
    import skill.retrieval.engine as engine

    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )
    plan = replace(
        base_plan,
        per_source_timeout_seconds=9.0,
        overall_deadline_seconds=12.0,
        mixed_pooled_enabled=True,
    )
    observed: dict[str, object] = {}

    async def _fake_run_first_wave(**kwargs: object) -> dict[str, SourceExecutionResult]:
        observed["first_wave_timeout"] = kwargs["overall_timeout_seconds"]
        return {
            "policy_official_registry": SourceExecutionResult(
                source_id="policy_official_registry",
                status="success",
                hits=(
                    _hit(
                        source_id="policy_official_registry",
                        title="policy-fragment",
                    ),
                ),
            ),
            "industry_ddgs": SourceExecutionResult(
                source_id="industry_ddgs",
                status="success",
                hits=(
                    _hit(
                        source_id="industry_ddgs",
                        title="industry-fragment",
                    ),
                ),
            ),
        }

    async def _fake_run_mixed_pooled_path(**kwargs: object):
        observed["pooled_called"] = True
        observed["pooled_first_wave_sources"] = tuple(
            kwargs["first_wave_results"].keys()
        )
        return engine.RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=(
                _hit(
                    source_id="policy_official_registry",
                    title="pooled-policy",
                ),
                _hit(
                    source_id="industry_ddgs",
                    title="pooled-industry",
                ),
            ),
            source_results=(),
        )

    monkeypatch.setattr(engine, "_run_first_wave", _fake_run_first_wave)
    monkeypatch.setattr(engine, "_run_mixed_pooled_path", _fake_run_mixed_pooled_path)

    outcome = asyncio.run(
        engine.run_retrieval(
            plan=plan,
            query="EU DORA ICT incident reporting timeline and SaaS vendor incident update notice",
            adapter_registry={},
        )
    )

    assert observed["first_wave_timeout"] == 2.5
    assert observed["pooled_called"] is True
    assert observed["pooled_first_wave_sources"] == (
        "policy_official_registry",
        "industry_ddgs",
    )
    assert outcome.status == "success"
    assert [item.title for item in outcome.results] == [
        "pooled-policy",
        "pooled-industry",
    ]


def test_run_retrieval_falls_back_to_standard_path_when_pooled_hook_returns_none(
    monkeypatch,
) -> None:
    import skill.retrieval.engine as engine

    base_plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )
    plan = replace(
        base_plan,
        per_source_timeout_seconds=9.0,
        overall_deadline_seconds=12.0,
        mixed_pooled_enabled=True,
    )

    async def _fake_run_first_wave(**_: object) -> dict[str, SourceExecutionResult]:
        return {
            "policy_official_registry": SourceExecutionResult(
                source_id="policy_official_registry",
                status="success",
                hits=(
                    _hit(
                        source_id="policy_official_registry",
                        title="policy-fragment",
                    ),
                ),
            ),
            "industry_ddgs": SourceExecutionResult(
                source_id="industry_ddgs",
                status="success",
                hits=(
                    _hit(
                        source_id="industry_ddgs",
                        title="industry-fragment",
                    ),
                ),
            ),
        }

    async def _fake_run_mixed_pooled_path(**_: object):
        return None

    monkeypatch.setattr(engine, "_run_first_wave", _fake_run_first_wave)
    monkeypatch.setattr(engine, "_run_mixed_pooled_path", _fake_run_mixed_pooled_path)

    outcome = asyncio.run(
        engine.run_retrieval(
            plan=plan,
            query="EU DORA ICT incident reporting timeline and SaaS vendor incident update notice",
            adapter_registry={},
        )
    )

    assert outcome.status == "success"
    assert [item.title for item in outcome.results] == [
        "policy-fragment",
        "industry-fragment",
    ]


def test_run_retrieval_keeps_mixed_pooled_hook_disabled_by_default(monkeypatch) -> None:
    import skill.retrieval.engine as engine

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="industry",
            reason_code="mixed_keywords",
            scores={"policy": 4, "academic": 0, "industry": 4},
        )
    )

    async def _fake_run_first_wave(**_: object) -> dict[str, SourceExecutionResult]:
        return {
            "policy_official_registry": SourceExecutionResult(
                source_id="policy_official_registry",
                status="success",
                hits=(
                    _hit(
                        source_id="policy_official_registry",
                        title="policy-fragment",
                    ),
                ),
            ),
            "industry_ddgs": SourceExecutionResult(
                source_id="industry_ddgs",
                status="success",
                hits=(
                    _hit(
                        source_id="industry_ddgs",
                        title="industry-fragment",
                    ),
                ),
            ),
        }

    async def _unexpected_pooled(**_: object):
        raise AssertionError("mixed pooled hook should be disabled by default")

    monkeypatch.setattr(engine, "_run_first_wave", _fake_run_first_wave)
    monkeypatch.setattr(engine, "_run_mixed_pooled_path", _unexpected_pooled)

    outcome = asyncio.run(
        engine.run_retrieval(
            plan=plan,
            query="EU DORA ICT incident reporting timeline and SaaS vendor incident update notice",
            adapter_registry={},
        )
    )

    assert outcome.status == "success"
    assert [item.title for item in outcome.results] == [
        "policy-fragment",
        "industry-fragment",
    ]


def test_mixed_pooled_path_builds_dual_route_shortlist_from_first_wave_hits() -> None:
    import skill.retrieval.engine as engine

    query = "EU DORA ICT incident reporting timeline and SaaS vendor incident update notice"
    plan = replace(
        build_retrieval_plan(
            ClassificationResult(
                route_label="mixed",
                primary_route="policy",
                supplemental_route="industry",
                reason_code="mixed_keywords",
                scores={"policy": 4, "academic": 0, "industry": 4},
            )
        ),
        mixed_shortlist_top_k=2,
    )

    first_wave_results = {
        "policy_official_registry": SourceExecutionResult(
            source_id="policy_official_registry",
            status="success",
            hits=(
                RetrievalHit(
                    source_id="policy_official_registry",
                    title="EU cyber policy overview",
                    url="https://example.com/policy-overview",
                    snippet="Overview of EU cyber policy obligations and notices.",
                    target_route="policy",
                    variant_reason_codes=("original",),
                    variant_queries=(query,),
                ),
                RetrievalHit(
                    source_id="policy_official_registry",
                    title="DORA ICT incident reporting timeline",
                    url="https://example.com/dora-reporting",
                    snippet="DORA incident reporting timeline and regulator deadlines.",
                    target_route="policy",
                    variant_reason_codes=("cross_domain_fragment_focus",),
                    variant_queries=("EU DORA ICT incident reporting timeline",),
                ),
            ),
        ),
        "industry_ddgs": SourceExecutionResult(
            source_id="industry_ddgs",
            status="success",
            hits=(
                RetrievalHit(
                    source_id="industry_ddgs",
                    title="Cloud vendor security communications",
                    url="https://example.com/cloud-communications",
                    snippet="General guidance on cloud vendor security communications.",
                    target_route="industry",
                    variant_reason_codes=("original",),
                    variant_queries=(query,),
                ),
                RetrievalHit(
                    source_id="industry_ddgs",
                    title="SaaS vendor incident update notice",
                    url="https://example.com/saas-incident-notice",
                    snippet="Vendor incident update notice and customer security release cadence.",
                    target_route="industry",
                    variant_reason_codes=("cross_domain_fragment_focus",),
                    variant_queries=("SaaS vendor incident update notice",),
                ),
            ),
        ),
    }

    async def _run():
        return await engine._run_mixed_pooled_path(
            plan=plan,
            query=query,
            first_wave_steps=plan.first_wave_sources,
            first_wave_results=first_wave_results,
            adapter_registry={},
            deadline_at=asyncio.get_running_loop().time() + 1.0,
        )

    outcome = asyncio.run(_run())

    assert outcome is not None
    assert outcome.status == "success"
    assert [item.title for item in outcome.results] == [
        "DORA ICT incident reporting timeline",
        "SaaS vendor incident update notice",
    ]
    assert {item.target_route for item in outcome.results} == {"policy", "industry"}
    assert all(
        "cross_domain_fragment_focus" in item.variant_reason_codes
        for item in outcome.results
    )


def test_mixed_pooled_path_returns_none_when_dual_route_hits_are_too_weak() -> None:
    import skill.retrieval.engine as engine

    query = "EU DORA ICT incident reporting timeline and SaaS vendor incident update notice"
    plan = replace(
        build_retrieval_plan(
            ClassificationResult(
                route_label="mixed",
                primary_route="policy",
                supplemental_route="industry",
                reason_code="mixed_keywords",
                scores={"policy": 4, "academic": 0, "industry": 4},
            )
        ),
        mixed_shortlist_top_k=2,
    )

    first_wave_results = {
        "policy_official_registry": SourceExecutionResult(
            source_id="policy_official_registry",
            status="success",
            hits=(
                RetrievalHit(
                    source_id="policy_official_registry",
                    title="EU cyber policy overview",
                    url="https://example.com/policy-overview",
                    snippet="Overview of EU cyber policy obligations and notices.",
                    target_route="policy",
                    variant_reason_codes=("original",),
                    variant_queries=(query,),
                ),
            ),
        ),
        "industry_ddgs": SourceExecutionResult(
            source_id="industry_ddgs",
            status="success",
            hits=(
                RetrievalHit(
                    source_id="industry_ddgs",
                    title="Cloud vendor security communications",
                    url="https://example.com/cloud-communications",
                    snippet="General guidance on cloud vendor security communications.",
                    target_route="industry",
                    variant_reason_codes=("original",),
                    variant_queries=(query,),
                ),
            ),
        ),
    }

    async def _run():
        return await engine._run_mixed_pooled_path(
            plan=plan,
            query=query,
            first_wave_steps=plan.first_wave_sources,
            first_wave_results=first_wave_results,
            adapter_registry={},
            deadline_at=asyncio.get_running_loop().time() + 1.0,
        )

    outcome = asyncio.run(_run())

    assert outcome is None
