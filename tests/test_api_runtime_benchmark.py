"""Phase 5 endpoint-path benchmark regressions."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from skill.benchmark.harness import load_benchmark_cases, run_benchmark_suite
from skill.benchmark.report import summarize_benchmark_runs
from skill.benchmark.repeatability import evaluate_repeatability
from skill.orchestrator.intent import ClassificationResult
from skill.retrieval.models import RetrievalHit
from skill.synthesis.cache import ANSWER_CACHE

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_phase5_cases.json"


class _DeterministicModelClient:
    def __init__(self) -> None:
        self.call_count = 0

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        self.call_count += 1
        return json.dumps(
            {
                "conclusion": "Deterministic benchmark draft.",
                "key_points": [
                    {
                        "key_point_id": "kp-1",
                        "statement": "Deterministic draft without citations.",
                        "citations": [],
                    }
                ],
                "sources": [],
                "uncertainty_notes": [],
            }
        )


def _classify_query(query: str) -> ClassificationResult:
    by_query = {
        "latest climate order version": ("policy", "policy", None),
        "latest methane registry update": ("policy", "policy", None),
        "industrial emissions guidance effective date": ("policy", "policy", None),
        "grounded search evidence packing paper": ("academic", "academic", None),
        "evidence normalization benchmark paper": ("academic", "academic", None),
        "latency-aware retrieval paper": ("academic", "academic", None),
        "semiconductor packaging capacity forecast 2026": ("industry", "industry", None),
        "battery recycling market share 2025": ("industry", "industry", None),
        "autonomous driving policy impact on industry": ("mixed", "policy", "industry"),
        "AI chip export controls effect on academic research": ("mixed", "policy", "academic"),
    }
    route_label, primary_route, supplemental_route = by_query[query]
    return ClassificationResult(
        route_label=route_label,
        primary_route=primary_route,
        supplemental_route=supplemental_route,
        reason_code=f"{route_label}_fixture",
        scores={"policy": 1, "academic": 1, "industry": 1},
    )


def _make_adapter(source_id: str):
    async def _adapter(query: str) -> list[RetrievalHit]:
        if source_id == "industry_ddgs" and query == "battery recycling market share 2025":
            return []
        if source_id == "academic_semantic_scholar" and query == "AI chip export controls effect on academic research":
            return []
        return [
            RetrievalHit(
                source_id=source_id,
                title=f"{source_id} title for {query}",
                url=f"https://example.com/{source_id}/{abs(hash(query))}",
                snippet=f"Deterministic evidence for {query} from {source_id}.",
                authority="State Council" if source_id.startswith("policy") else None,
                jurisdiction="CN" if source_id.startswith("policy") else None,
                publication_date="2026-04-01" if source_id.startswith("policy") else None,
                effective_date="2026-05-01" if source_id.startswith("policy") else None,
                version="2026-04 edition" if source_id.startswith("policy") else None,
                doi="10.1000/fake" if source_id.startswith("academic") else None,
                arxiv_id="2604.12345" if source_id.startswith("academic") else None,
                first_author="Lin" if source_id.startswith("academic") else None,
                year=2026 if source_id.startswith("academic") else None,
                evidence_level="peer_reviewed" if source_id.startswith("academic") else None,
            )
        ]

    return _adapter


def test_api_runtime_benchmark_uses_live_answer_path_and_keeps_telemetry_internal(
    monkeypatch,
    tmp_path,
) -> None:
    import skill.api.entry as api_entry

    ANSWER_CACHE.clear()
    cases = load_benchmark_cases(FIXTURE_PATH)
    model_client = _DeterministicModelClient()

    monkeypatch.setattr(api_entry, "classify_query", _classify_query)
    api_entry.app.state.adapter_registry = {
        "policy_official_registry": _make_adapter("policy_official_registry"),
        "policy_official_web_allowlist_fallback": _make_adapter(
            "policy_official_web_allowlist_fallback"
        ),
        "academic_asta_mcp": _make_adapter("academic_asta_mcp"),
        "academic_semantic_scholar": _make_adapter("academic_semantic_scholar"),
        "academic_arxiv": _make_adapter("academic_arxiv"),
        "industry_ddgs": _make_adapter("industry_ddgs"),
    }
    api_entry.app.state.model_client = model_client

    try:
        client = TestClient(api_entry.app)
        payload = client.post(
            "/answer",
            json={"query": cases[0].query},
        ).json()

        records = run_benchmark_suite(
            app=api_entry.app,
            cases=cases,
            runs=5,
            output_dir=tmp_path,
        )
    finally:
        ANSWER_CACHE.clear()
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    assert len(records) == 50
    assert Counter(record.case_id for record in records) == {
        case.case_id: 5 for case in cases
    }

    assert "runtime_trace" not in payload
    assert "latency_budget_ok" not in payload
    assert "token_budget_ok" not in payload
    assert "evidence_token_estimate" not in payload
    assert "answer_token_estimate" not in payload
    assert "retrieval_trace" not in payload

    first_record = records[0].model_dump()
    assert "latency_budget_ok" in first_record
    assert "token_budget_ok" in first_record
    assert "evidence_token_estimate" in first_record
    assert "answer_token_estimate" in first_record
    assert "retrieval_trace" in first_record
    assert isinstance(first_record["retrieval_trace"], list)
    assert first_record["retrieval_trace"]
    assert {
        "source_id",
        "stage",
        "started_at_ms",
        "elapsed_ms",
        "hit_count",
        "error_class",
        "was_cancelled_by_deadline",
    } <= set(first_record["retrieval_trace"][0])

    summary = summarize_benchmark_runs(records)
    assert summary.answer_status_breakdown
    assert isinstance(summary.failure_reason_breakdown, dict)

    repeatability = evaluate_repeatability(records)
    assert repeatability["all_repeatable"] is True
    assert model_client.call_count < len(records)


def test_answer_endpoint_reuses_cached_grounded_success_for_normalized_queries(
    monkeypatch,
) -> None:
    import skill.api.entry as api_entry

    ANSWER_CACHE.clear()
    adapter_call_count = 0

    async def _policy_adapter(_: str) -> list[RetrievalHit]:
        nonlocal adapter_call_count
        adapter_call_count += 1
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
            raise AssertionError("policy fast path should skip generation")

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
        first = client.post("/answer", json={"query": "latest climate order version"})
        calls_after_first = adapter_call_count
        second = client.post(
            "/answer",
            json={"query": "  LATEST   climate ORDER version  "},
        )
    finally:
        ANSWER_CACHE.clear()
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls_after_first > 0
    assert adapter_call_count == calls_after_first
    second_payload = second.json()
    assert second_payload["answer_status"] == "grounded_success"
    assert "runtime_trace" not in second_payload
    assert "latency_budget_ok" not in second_payload
    assert "token_budget_ok" not in second_payload
    assert "retrieval_trace" not in second_payload
