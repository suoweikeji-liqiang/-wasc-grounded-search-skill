"""Phase 5 answer-runtime budget regressions."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from skill.api.schema import RetrieveResponse
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import run_retrieval
from skill.retrieval.models import RetrievalHit
from skill.synthesis.generator import ModelBackendError


def _build_plan(route_label: str, primary_route: str, supplemental_route: str | None):
    return build_retrieval_plan(
        ClassificationResult(
            route_label=route_label,
            primary_route=primary_route,
            supplemental_route=supplemental_route,
            reason_code=f"{route_label}_keywords",
            scores={"policy": 1, "industry": 1, "academic": 1},
        )
    )


def _grounded_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "Climate Order 2026",
                "canonical_url": "https://www.gov.cn/policy/climate-order-2026",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "The Climate Order takes effect on May 1, 2026.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _policy_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "Ministry of Ecology and Environment policy bulletin",
                "canonical_url": "https://www.mee.gov.cn/policy/latest-regulation",
                "route_role": "primary",
                "authority": "Ministry of Ecology and Environment",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-03-18",
                "effective_date": "2026-04-01",
                "version": "2026-03 bulletin",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Official regulatory bulletin for environmental compliance.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "policy-2",
                "domain": "policy",
                "canonical_title": "State Council administrative regulation repository update",
                "canonical_url": "https://www.gov.cn/zhengce/content/official-update.htm",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-02-21",
                "effective_date": "2026-03-01",
                "version": None,
                "version_status": "version_missing",
                "retained_slices": [
                    {
                        "text": "Authoritative policy text with publication references.",
                        "source_record_id": "policy-2-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _academic_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "paper-1",
                "domain": "academic",
                "canonical_title": "Evidence normalization for retrieval grounded systems",
                "canonical_url": "https://www.semanticscholar.org/paper/abc123",
                "route_role": "primary",
                "evidence_level": "peer_reviewed",
                "canonical_match_confidence": "heuristic",
                "doi": "10.48550/wasc.2025.001",
                "first_author": "Lin",
                "year": 2025,
                "retained_slices": [
                    {
                        "text": "Peer-reviewed study on merging policy and academic evidence signals.",
                        "source_record_id": "paper-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _academic_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="academic",
        primary_route="academic",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "paper-1",
                "domain": "academic",
                "canonical_title": "Evidence normalization for retrieval grounded systems",
                "canonical_url": "https://www.semanticscholar.org/paper/abc123",
                "route_role": "primary",
                "evidence_level": "peer_reviewed",
                "canonical_match_confidence": "heuristic",
                "doi": "10.48550/wasc.2025.001",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2025,
                "retained_slices": [
                    {
                        "text": "Peer-reviewed study on merging policy and academic evidence signals.",
                        "source_record_id": "paper-1-slice-1",
                        "source_span": "snippet",
                    },
                    {
                        "text": "Preprint variant of the evidence normalization study before journal publication.",
                        "source_record_id": "paper-1-slice-2",
                        "source_span": "snippet",
                    },
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _industry_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="industry",
        primary_route="industry",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "industry-1",
                "domain": "industry",
                "canonical_title": "Battery recycling market share outlook 2025",
                "canonical_url": "https://www.reuters.com/markets/battery-recycling-share-2025",
                "route_role": "primary",
                "retained_slices": [
                    {
                        "text": "Trusted news estimate of battery recycling market-share shifts in 2025.",
                        "source_record_id": "industry-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "industry-2",
                "domain": "industry",
                "canonical_title": "Tesla annual battery supply update",
                "canonical_url": "https://www.tesla.com/blog/battery-supply-update",
                "route_role": "primary",
                "retained_slices": [
                    {
                        "text": "Company disclosure on battery production guidance.",
                        "source_record_id": "industry-2-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _mixed_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "State Council autonomous driving pilot regulation",
                "canonical_url": "https://www.gov.cn/zhengce/autonomous-driving-pilot-regulation",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-03-28",
                "effective_date": "2026-05-01",
                "version": "2026 pilot edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Official autonomous driving pilot regulation sets 2026 compliance requirements for road testing.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "industry-1",
                "domain": "industry",
                "canonical_title": "BYD autonomous driving supplier investment update",
                "canonical_url": "https://www.byd.com/news/autonomous-driving-supplier-investment-2026",
                "route_role": "supplemental",
                "retained_slices": [
                    {
                        "text": "Company update says autonomous driving programs are increasing supplier investment across the vehicle industry in 2026.",
                        "source_record_id": "industry-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=True,
        evidence_pruned=False,
    )


def _mixed_weak_overlap_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-1",
                "domain": "policy",
                "canonical_title": "State Council administrative regulation repository update",
                "canonical_url": "https://www.gov.cn/zhengce/content/official-update.htm",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-02-21",
                "effective_date": "2026-03-01",
                "version": None,
                "version_status": "version_missing",
                "retained_slices": [
                    {
                        "text": "Authoritative policy text with publication references.",
                        "source_record_id": "policy-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "industry-1",
                "domain": "industry",
                "canonical_title": "Tesla annual battery supply update",
                "canonical_url": "https://www.tesla.com/blog/battery-supply-update",
                "route_role": "supplemental",
                "retained_slices": [
                    {
                        "text": "Company disclosure on battery production guidance.",
                        "source_record_id": "industry-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _policy_chinese_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-cn-1",
                "domain": "policy",
                "canonical_title": "\u6c14\u5019\u547d\u4ee4\u4fee\u8ba2\u901a\u544a",
                "canonical_url": "https://www.gov.cn/zhengce/climate-order-revision",
                "route_role": "primary",
                "authority": "\u56fd\u52a1\u9662",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-03-18",
                "effective_date": "2026-04-01",
                "version": "2026-03 \u4fee\u8ba2\u7248",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "\u6b63\u5f0f\u7248\u6c14\u5019\u547d\u4ee4\u4fee\u8ba2\u7248\u5c06\u4e8e 2026-04-01 \u751f\u6548\u3002",
                        "source_record_id": "policy-cn-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


def _mixed_chinese_fast_path_retrieve_response() -> RetrieveResponse:
    return RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-cn-1",
                "domain": "policy",
                "canonical_title": "\u81ea\u52a8\u9a7e\u9a76\u8bd5\u70b9\u76d1\u7ba1\u529e\u6cd5\u4fee\u8ba2",
                "canonical_url": "https://www.gov.cn/zhengce/autonomous-driving-amendment",
                "route_role": "primary",
                "authority": "\u56fd\u52a1\u9662",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-03-28",
                "effective_date": "2026-05-01",
                "version": "2026 \u8bd5\u70b9\u7248",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "\u81ea\u52a8\u9a7e\u9a76\u76d1\u7ba1\u53d8\u5316\u5c06\u5f71\u54cd 2026 \u5e74\u8bd5\u70b9\u843d\u5730\u3002",
                        "source_record_id": "policy-cn-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "industry-cn-1",
                "domain": "industry",
                "canonical_title": "\u81ea\u52a8\u9a7e\u9a76\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd\u9884\u6d4b",
                "canonical_url": "https://www.example.com/autonomous-driving-industry-impact",
                "route_role": "supplemental",
                "retained_slices": [
                    {
                        "text": "\u4f9b\u5e94\u94fe\u5382\u5546\u9884\u8ba1\u76d1\u7ba1\u8bd5\u70b9\u5c06\u63a8\u52a8\u81ea\u52a8\u9a7e\u9a76\u4ea7\u4e1a\u843d\u5730\u3002",
                        "source_record_id": "industry-cn-1-slice-1",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
        ],
        evidence_clipped=False,
        evidence_pruned=False,
    )


class _RecordingModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call_count = 0
        self.timeouts: list[float | None] = []

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        self.call_count += 1
        self.timeouts.append(timeout_seconds)
        return json.dumps(self.payload)


def test_execute_answer_pipeline_with_trace_forwards_remaining_synthesis_timeout(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "The Climate Order takes effect on May 1, 2026.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
                        }
                    ],
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "Climate Order 2026",
                    "url": "https://www.gov.cn/policy/climate-order-2026",
                }
            ],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="climate takes effect on May 1",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 1
    assert model_client.timeouts[0] is not None
    assert 1.5 <= model_client.timeouts[0] <= 2.0
    assert result.response.answer_status == "grounded_success"
    assert result.runtime_trace.latency_budget_ok is True
    assert result.runtime_trace.token_budget_ok is True
    assert result.runtime_trace.evidence_token_estimate > 0
    assert result.runtime_trace.answer_token_estimate is not None


def test_execute_answer_pipeline_with_trace_enforces_answer_token_budget(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": (
                "The Climate Order takes effect on May 1, 2026 and applies "
                "across the full reporting window with additional obligations."
            ),
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
                        }
                    ],
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "Climate Order 2026",
                    "url": "https://www.gov.cn/policy/climate-order-2026",
                }
            ],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="climate takes effect on May 1",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(answer_token_budget=3),
        )
    )

    assert model_client.call_count == 1
    assert result.response.answer_status == "insufficient_evidence"
    assert (
        result.response.conclusion
        == "Available runtime budget was insufficient to complete grounded synthesis."
    )
    assert any(
        note.startswith("Budget enforcement:")
        for note in result.response.uncertainty_notes
    )
    assert result.runtime_trace.token_budget_ok is False
    assert result.runtime_trace.budget_exhausted_phase == "answer_tokens"


def test_execute_answer_pipeline_with_trace_skips_generation_for_irrelevant_evidence(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="battery recycling market share 2025",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.key_points == []
    assert result.response.sources == []
    assert any(
        note.startswith("Relevance gate:")
        for note in result.response.uncertainty_notes
    )
    assert result.runtime_trace.budget_exhausted_phase is None
    assert result.runtime_trace.latency_budget_ok is True


def test_execute_answer_pipeline_with_trace_skips_generation_on_single_term_overlap(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="climate battery share",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert any(
        note.startswith("Relevance gate:")
        for note in result.response.uncertainty_notes
    )


def test_execute_answer_pipeline_with_trace_uses_policy_lookup_fast_path(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _policy_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "policy lookup fast path should skip grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="latest climate order version",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert (
        'Closest retained policy match: "Ministry of Ecology and Environment policy bulletin"'
        in result.response.conclusion
    )
    assert "2026-03 bulletin" in result.response.conclusion
    assert "2026-04-01" in result.response.conclusion
    assert result.response.key_points[0].model_dump() == {
        "key_point_id": "kp-1",
        "statement": "Official regulatory bulletin for environmental compliance.",
        "citations": [
            {
                "evidence_id": "policy-1",
                "source_record_id": "policy-1-slice-1",
                "source_url": "https://www.mee.gov.cn/policy/latest-regulation",
                "quote_text": "Official regulatory bulletin for environmental compliance.",
            }
        ],
    }
    assert result.response.sources[0].model_dump() == {
        "evidence_id": "policy-1",
        "title": "Ministry of Ecology and Environment policy bulletin",
        "url": "https://www.mee.gov.cn/policy/latest-regulation",
    }
    assert result.runtime_trace.latency_budget_ok is True


def test_execute_answer_pipeline_with_trace_uses_policy_lookup_fast_path_for_chinese_version_query(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _policy_chinese_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "Chinese policy lookup should use the local fast path"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="\u6c14\u5019\u547d\u4ee4\u6700\u65b0\u7248\u672c\u4ec0\u4e48\u65f6\u5019\u751f\u6548",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert "\u6c14\u5019\u547d\u4ee4\u4fee\u8ba2\u901a\u544a" in result.response.conclusion
    assert "2026-03 \u4fee\u8ba2\u7248" in result.response.conclusion
    assert "2026-04-01" in result.response.conclusion


def test_execute_answer_pipeline_with_trace_uses_industry_lookup_fast_path(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _industry_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "industry lookup fast path should skip grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("industry", "industry", None),
            query="battery recycling market share 2025",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert (
        'Closest retained industry match: "Battery recycling market share outlook 2025"'
        in result.response.conclusion
    )
    assert result.response.key_points[0].model_dump() == {
        "key_point_id": "kp-1",
        "statement": "Trusted news estimate of battery recycling market-share shifts in 2025.",
        "citations": [
            {
                "evidence_id": "industry-1",
                "source_record_id": "industry-1-slice-1",
                "source_url": "https://www.reuters.com/markets/battery-recycling-share-2025",
                "quote_text": "Trusted news estimate of battery recycling market-share shifts in 2025.",
            }
        ],
    }
    assert result.response.sources[0].model_dump() == {
        "evidence_id": "industry-1",
        "title": "Battery recycling market share outlook 2025",
        "url": "https://www.reuters.com/markets/battery-recycling-share-2025",
    }
    assert result.runtime_trace.latency_budget_ok is True


def test_execute_answer_pipeline_with_trace_uses_mixed_cross_domain_fast_path(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _mixed_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "mixed cross-domain fast path should skip grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query="autonomous driving policy impact on industry",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert (
        "State Council autonomous driving pilot regulation"
        in result.response.conclusion
    )
    assert (
        "BYD autonomous driving supplier investment update"
        in result.response.conclusion
    )
    assert len(result.response.key_points) == 2
    assert {
        source["title"] for source in [item.model_dump() for item in result.response.sources]
    } == {
        "State Council autonomous driving pilot regulation",
        "BYD autonomous driving supplier investment update",
    }
    assert result.runtime_trace.latency_budget_ok is True


def test_execute_answer_pipeline_with_trace_uses_mixed_cross_domain_fast_path_for_chinese_impact_query(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _mixed_chinese_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "Chinese mixed impact query should use the local fast path"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query=(
                "\u81ea\u52a8\u9a7e\u9a76\u653f\u7b56\u53d8\u5316"
                "\u5bf9\u4ea7\u4e1a\u843d\u5730\u6709\u4ec0\u4e48\u5f71\u54cd"
            ),
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert "\u81ea\u52a8\u9a7e\u9a76\u8bd5\u70b9\u76d1\u7ba1\u529e\u6cd5\u4fee\u8ba2" in result.response.conclusion
    assert "\u81ea\u52a8\u9a7e\u9a76\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd\u9884\u6d4b" in result.response.conclusion


def test_execute_answer_pipeline_with_trace_keeps_mixed_fast_path_conservative(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _mixed_weak_overlap_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("mixed", "policy", "industry"),
            query="autonomous driving policy impact on industry",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert any(
        note.startswith("Relevance gate:")
        for note in result.response.uncertainty_notes
    )


def test_execute_answer_pipeline_with_trace_degrades_on_generation_backend_error(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _grounded_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _FailingModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise ModelBackendError("MiniMax request failed with status 500")

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("policy", "policy", None),
            query="The Climate Order takes effect on May 1, 2026.",
            adapter_registry={},
            model_client=_FailingModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "insufficient_evidence"
    assert result.response.key_points == []
    assert any(
        note.startswith("Generation backend:")
        for note in result.response.uncertainty_notes
    )
    assert result.runtime_trace.budget_exhausted_phase is None


def test_execute_answer_pipeline_with_trace_skips_academic_generation_when_slice_overlap_is_weak(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _academic_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    model_client = _RecordingModelClient(
        {
            "conclusion": "This response should never be generated.",
            "key_points": [],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("academic", "academic", None),
            query="grounded search evidence packing paper",
            adapter_registry={},
            model_client=model_client,
            runtime_budget=RuntimeBudget(),
        )
    )

    assert model_client.call_count == 0
    assert result.response.answer_status == "insufficient_evidence"
    assert any(
        note.startswith("Relevance gate:")
        for note in result.response.uncertainty_notes
    )


def test_execute_answer_pipeline_with_trace_uses_academic_lookup_fast_path(
    monkeypatch,
) -> None:
    import skill.synthesis.orchestrate as synthesis_orchestrate
    from skill.orchestrator.budget import RuntimeBudget
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    async def _fake_execute_retrieval_pipeline(**_: object) -> RetrieveResponse:
        return _academic_fast_path_retrieve_response()

    monkeypatch.setattr(
        synthesis_orchestrate,
        "execute_retrieval_pipeline",
        _fake_execute_retrieval_pipeline,
    )

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "academic title lookup fast path should skip grounded synthesis"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("academic", "academic", None),
            query="evidence normalization benchmark paper",
            adapter_registry={},
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert (
        "Evidence normalization for retrieval grounded systems"
        in result.response.conclusion
    )
    assert result.response.key_points[0].model_dump() == {
        "key_point_id": "kp-1",
        "statement": "Preprint variant of the evidence normalization study before journal publication.",
        "citations": [
            {
                "evidence_id": "paper-1",
                "source_record_id": "paper-1-slice-2",
                "source_url": "https://www.semanticscholar.org/paper/abc123",
                "quote_text": "Preprint variant of the evidence normalization study before journal publication.",
            }
        ],
    }
    assert result.response.sources[0].model_dump() == {
        "evidence_id": "paper-1",
        "title": "Evidence normalization for retrieval grounded systems",
        "url": "https://www.semanticscholar.org/paper/abc123",
    }
    assert result.runtime_trace.latency_budget_ok is True


def test_execute_answer_pipeline_with_trace_uses_academic_lookup_fast_path_for_grounded_search_evidence_packing() -> None:
    from skill.orchestrator.budget import RuntimeBudget
    from skill.retrieval.adapters.academic_arxiv import search as arxiv_search
    from skill.retrieval.adapters.academic_semantic_scholar import (
        search as semantic_scholar_search,
    )
    from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError(
                "grounded search evidence packing should use the academic fast path"
            )

    result = asyncio.run(
        execute_answer_pipeline_with_trace(
            plan=_build_plan("academic", "academic", None),
            query="grounded search evidence packing paper",
            adapter_registry={
                "academic_semantic_scholar": semantic_scholar_search,
                "academic_arxiv": arxiv_search,
            },
            model_client=_NeverCalledModelClient(),
            runtime_budget=RuntimeBudget(),
        )
    )

    assert result.response.answer_status == "grounded_success"
    assert "Grounded search evidence packing" in result.response.conclusion
    assert result.response.sources[0].title == "Grounded search evidence packing"
    assert result.runtime_trace.latency_budget_ok is True


def test_run_retrieval_propagates_cancelled_error() -> None:
    classification = ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 4, "academic": 0, "industry": 0},
    )
    base_plan = build_retrieval_plan(classification)
    first_step = base_plan.first_wave_sources[0]
    plan = replace(
        base_plan,
        first_wave_sources=(first_step,),
        fallback_sources=(),
        per_source_timeout_seconds=0.5,
        overall_deadline_seconds=0.5,
        global_concurrency_cap=1,
    )

    async def _cancelled(_: str) -> list[RetrievalHit]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_retrieval(
                plan=plan,
                query="latest climate order version",
                adapter_registry={first_step.source.source_id: _cancelled},
            )
        )


def test_answer_endpoint_stores_runtime_trace_and_omits_internal_budget_fields(
    monkeypatch,
) -> None:
    import skill.api.entry as api_entry

    monkeypatch.setenv("WASC_SYNTHESIS_DEADLINE_SECONDS", "0")

    def _unexpected_default_adapter_registry() -> dict[str, object]:
        raise AssertionError("default adapter registry should not be used")

    async def _policy_adapter(_: str) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                source_id="policy_official_registry",
                title="Climate Order 2026",
                url="https://www.gov.cn/policy/climate-order-2026",
                snippet="The Climate Order takes effect on May 1, 2026.",
                authority="State Council",
                jurisdiction="CN",
                publication_date="2026-04-01",
                effective_date="2026-05-01",
                version="2026-04 edition",
            )
        ]

    class _NeverCalledModelClient:
        def generate_text(
            self, prompt: str, timeout_seconds: float | None = None
        ) -> str:
            raise AssertionError("budget exhaustion should skip grounded synthesis")

    monkeypatch.setattr(
        api_entry,
        "_default_adapter_registry",
        _unexpected_default_adapter_registry,
    )
    monkeypatch.setattr(
        api_entry,
        "classify_query",
        lambda _query: ClassificationResult(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            reason_code="policy_hit",
            scores={"policy": 4, "academic": 0, "industry": 0},
        ),
    )

    api_entry.app.state.adapter_registry = {
        "policy_official_registry": _policy_adapter,
    }
    api_entry.app.state.model_client = _NeverCalledModelClient()

    try:
        client = TestClient(api_entry.app)
        response = client.post(
            "/answer",
            json={"query": "climate takes effect on May 1"},
        )
    finally:
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_status"] == "insufficient_evidence"
    assert any(
        note.startswith("Budget enforcement:")
        for note in payload["uncertainty_notes"]
    )
    assert "runtime_trace" not in payload
    assert "latency_budget_ok" not in payload
    assert "token_budget_ok" not in payload
    assert "evidence_token_estimate" not in payload
    assert "answer_token_estimate" not in payload

    runtime_trace = api_entry.app.state.last_runtime_trace
    assert runtime_trace.route_label == "policy"
    assert runtime_trace.answer_status == "insufficient_evidence"
    assert runtime_trace.budget_exhausted_phase == "synthesis"
    assert runtime_trace.evidence_token_estimate > 0
