"""Phase 5 benchmark harness regressions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import FastAPI

from skill.api.schema import AnswerRequest, AnswerResponse
from skill.orchestrator.budget import RuntimeTrace

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_phase5_cases.json"


def _build_fake_benchmark_app() -> FastAPI:
    app = FastAPI()

    @app.post("/answer", response_model=AnswerResponse)
    async def _answer(payload: AnswerRequest) -> AnswerResponse:
        app.state.last_runtime_trace = RuntimeTrace(
            request_id=f"trace-{payload.query}",
            route_label="policy",
            answer_status="grounded_success",
            retrieval_status="success",
            elapsed_ms=120,
            retrieval_elapsed_ms=40,
            synthesis_elapsed_ms=80,
            evidence_token_estimate=24,
            answer_token_estimate=18,
            latency_budget_ok=True,
            token_budget_ok=True,
            failure_reason=None,
            budget_exhausted_phase=None,
        )
        return AnswerResponse(
            answer_status="grounded_success",
            retrieval_status="success",
            failure_reason=None,
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            conclusion=f"Grounded answer for {payload.query}",
            key_points=[],
            sources=[],
            uncertainty_notes=[],
            gaps=[],
        )

    return app


def test_load_benchmark_cases_preserves_locked_manifest_order() -> None:
    from skill.benchmark.harness import load_benchmark_cases

    cases = load_benchmark_cases(FIXTURE_PATH)

    assert [case.case_id for case in cases] == [
        "policy-01",
        "policy-02",
        "policy-03",
        "academic-01",
        "academic-02",
        "academic-03",
        "industry-01",
        "industry-02",
        "mixed-01",
        "mixed-02",
    ]
    assert [case.query for case in cases] == [
        "latest climate order version",
        "latest methane registry update",
        "industrial emissions guidance effective date",
        "grounded search evidence packing paper",
        "evidence normalization benchmark paper",
        "latency-aware retrieval paper",
        "semiconductor packaging capacity forecast 2026",
        "battery recycling market share 2025",
        "autonomous driving policy impact on industry",
        "AI chip export controls effect on academic research",
    ]


def test_run_benchmark_suite_emits_10x5_records_with_required_runtime_fields(
    tmp_path,
) -> None:
    from skill.benchmark.harness import load_benchmark_cases, run_benchmark_suite

    app = _build_fake_benchmark_app()
    cases = load_benchmark_cases(FIXTURE_PATH)

    records = run_benchmark_suite(
        app=app,
        cases=cases,
        runs=5,
        output_dir=tmp_path,
    )

    assert len(records) == 50
    assert Counter(record.case_id for record in records) == {
        case.case_id: 5 for case in cases
    }
    assert Counter(record.run_index for record in records) == {
        1: 10,
        2: 10,
        3: 10,
        4: 10,
        5: 10,
    }

    first_record = records[0].model_dump()
    assert set(first_record) == {
        "case_id",
        "run_index",
        "query",
        "route_label",
        "answer_status",
        "retrieval_status",
        "success",
        "elapsed_ms",
        "evidence_token_estimate",
        "answer_token_estimate",
        "latency_budget_ok",
        "token_budget_ok",
        "failure_reason",
    }
    assert first_record["latency_budget_ok"] is True
    assert first_record["token_budget_ok"] is True
    assert first_record["answer_token_estimate"] == 18
