"""Phase 5 benchmark harness regressions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess
import threading
import time

from fastapi import FastAPI

from skill.api.schema import AnswerRequest, AnswerResponse
from skill.orchestrator.budget import RuntimeTrace

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_phase5_cases.json"
HIDDEN_SMOKE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_hidden_style_smoke_cases.json"


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
            problem_structure="authoritative_lookup",
            claim_type="fact",
            answerability_status="met",
            evidence_slot_coverage=(
                {
                    "slot_id": "primary_evidence",
                    "required": True,
                    "filled": True,
                    "evidence_ids": ["policy-1"],
                },
            ),
            retrieval_trace=(
                {
                    "source_id": "policy_official_registry",
                    "stage": "first_wave",
                    "started_at_ms": 0,
                    "elapsed_ms": 40,
                    "hit_count": 1,
                    "error_class": "ok",
                    "was_cancelled_by_deadline": False,
                },
            ),
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


def test_load_hidden_style_smoke_cases_preserves_manifest_order() -> None:
    from skill.benchmark.harness import load_benchmark_cases

    cases = load_benchmark_cases(HIDDEN_SMOKE_FIXTURE_PATH)

    assert [case.case_id for case in cases] == [
        "smoke-policy-01",
        "smoke-policy-02",
        "smoke-academic-01",
        "smoke-academic-02",
        "smoke-industry-01",
        "smoke-industry-02",
        "smoke-mixed-01",
        "smoke-mixed-02",
    ]
    assert [case.expected_route for case in cases] == [
        "policy",
        "policy",
        "academic",
        "academic",
        "industry",
        "industry",
        "mixed",
        "mixed",
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
        "provider_prompt_tokens",
        "provider_completion_tokens",
        "provider_total_tokens",
        "problem_structure",
        "claim_type",
        "answerability_status",
        "evidence_slot_coverage",
        "retrieval_trace",
    }
    assert first_record["latency_budget_ok"] is True
    assert first_record["token_budget_ok"] is True
    assert first_record["answer_token_estimate"] == 18
    assert first_record["problem_structure"] == "authoritative_lookup"
    assert first_record["claim_type"] == "fact"
    assert first_record["answerability_status"] == "met"
    assert first_record["evidence_slot_coverage"] == [
        {
            "slot_id": "primary_evidence",
            "required": True,
            "filled": True,
            "evidence_ids": ["policy-1"],
        }
    ]
    assert first_record["retrieval_trace"] == [
        {
            "source_id": "policy_official_registry",
            "stage": "first_wave",
            "started_at_ms": 0,
            "elapsed_ms": 40,
            "hit_count": 1,
            "error_class": "ok",
            "was_cancelled_by_deadline": False,
        }
    ]


def test_run_benchmark_suite_fresh_process_runs_each_attempt_in_isolation(
    tmp_path,
    monkeypatch,
) -> None:
    import skill.benchmark.harness as harness
    from skill.benchmark.models import BenchmarkRunRecord

    cases = harness.load_benchmark_cases(HIDDEN_SMOKE_FIXTURE_PATH)[:2]
    observed_attempts: list[tuple[str, int, str]] = []

    class _UnexpectedTestClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("fresh-process benchmark mode should not reuse TestClient")

    def _fake_run_case_fresh_process(
        *,
        case,
        run_index: int,
        app_import_path: str,
    ) -> BenchmarkRunRecord:
        observed_attempts.append((case.case_id, run_index, app_import_path))
        return BenchmarkRunRecord(
            case_id=case.case_id,
            run_index=run_index,
            query=case.query,
            route_label=case.expected_route or "policy",
            answer_status="grounded_success",
            retrieval_status="success",
            success=True,
            elapsed_ms=95,
            evidence_token_estimate=12,
            answer_token_estimate=8,
            latency_budget_ok=True,
            token_budget_ok=True,
            failure_reason=None,
            provider_prompt_tokens=None,
            provider_completion_tokens=None,
            provider_total_tokens=None,
            retrieval_trace=[],
        )

    monkeypatch.setattr(harness, "TestClient", _UnexpectedTestClient)
    monkeypatch.setattr(
        harness,
        "_run_case_fresh_process",
        _fake_run_case_fresh_process,
        raising=False,
    )

    records = harness.run_benchmark_suite(
        app=_build_fake_benchmark_app(),
        cases=cases,
        runs=2,
        output_dir=tmp_path,
        fresh_process=True,
        app_import_path="skill.api.entry:app",
    )

    assert [(record.case_id, record.run_index) for record in records] == [
        ("smoke-policy-01", 1),
        ("smoke-policy-01", 2),
        ("smoke-policy-02", 1),
        ("smoke-policy-02", 2),
    ]
    assert observed_attempts == [
        ("smoke-policy-01", 1, "skill.api.entry:app"),
        ("smoke-policy-01", 2, "skill.api.entry:app"),
        ("smoke-policy-02", 1, "skill.api.entry:app"),
        ("smoke-policy-02", 2, "skill.api.entry:app"),
    ]


def test_run_benchmark_suite_fresh_process_supports_bounded_parallelism_and_preserves_order(
    tmp_path,
    monkeypatch,
) -> None:
    import skill.benchmark.harness as harness
    from skill.benchmark.models import BenchmarkRunRecord

    cases = harness.load_benchmark_cases(HIDDEN_SMOKE_FIXTURE_PATH)[:2]
    lock = threading.Lock()
    observed_completion_order: list[tuple[str, int]] = []
    active_calls = 0
    max_active_calls = 0

    def _fake_run_case_fresh_process(
        *,
        case,
        run_index: int,
        app_import_path: str,
    ) -> BenchmarkRunRecord:
        nonlocal active_calls, max_active_calls
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
        time.sleep(0.05 if run_index == 1 else 0.01)
        with lock:
            observed_completion_order.append((case.case_id, run_index))
            active_calls -= 1
        return BenchmarkRunRecord(
            case_id=case.case_id,
            run_index=run_index,
            query=case.query,
            route_label=case.expected_route or "policy",
            answer_status="grounded_success",
            retrieval_status="success",
            success=True,
            elapsed_ms=95,
            evidence_token_estimate=12,
            answer_token_estimate=8,
            latency_budget_ok=True,
            token_budget_ok=True,
            failure_reason=None,
            provider_prompt_tokens=None,
            provider_completion_tokens=None,
            provider_total_tokens=None,
            retrieval_trace=[],
        )

    monkeypatch.setattr(
        harness,
        "_run_case_fresh_process",
        _fake_run_case_fresh_process,
        raising=False,
    )

    records = harness.run_benchmark_suite(
        app=None,
        cases=cases,
        runs=2,
        output_dir=tmp_path,
        fresh_process=True,
        app_import_path="skill.api.entry:app",
        max_parallel=2,
    )

    expected_order = [
        ("smoke-policy-01", 1),
        ("smoke-policy-01", 2),
        ("smoke-policy-02", 1),
        ("smoke-policy-02", 2),
    ]
    assert max_active_calls == 2
    assert observed_completion_order != expected_order
    assert [(record.case_id, record.run_index) for record in records] == expected_order


def test_run_case_fresh_process_returns_timeout_record_when_worker_hangs(
    monkeypatch,
) -> None:
    import skill.benchmark.harness as harness

    case = harness.BenchmarkCase(
        case_id="smoke-industry-01",
        query="advanced packaging capacity outlook 2026",
        expected_route="industry",
    )

    def _timeout_subprocess_run(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(
            cmd=["python", "-m", "skill.benchmark.worker"],
            timeout=harness._FRESH_PROCESS_TIMEOUT_SECONDS,
        )

    monkeypatch.setattr(harness.subprocess, "run", _timeout_subprocess_run)

    record = harness._run_case_fresh_process(
        case=case,
        run_index=1,
        app_import_path="skill.api.entry:app",
    )

    assert record.case_id == "smoke-industry-01"
    assert record.route_label == "industry"
    assert record.answer_status == "retrieval_failure"
    assert record.retrieval_status == "failure_gaps"
    assert record.success is False
    assert record.failure_reason == "timeout"
    assert record.latency_budget_ok is False
    assert record.elapsed_ms == int(harness._FRESH_PROCESS_TIMEOUT_SECONDS * 1000)


def test_run_case_fresh_process_returns_failure_record_when_worker_exits_nonzero(
    monkeypatch,
) -> None:
    import skill.benchmark.harness as harness

    case = harness.BenchmarkCase(
        case_id="smoke-mixed-01",
        query="cross-border AI policy impact on chip supply chains",
        expected_route="mixed",
    )

    def _failing_subprocess_run(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["python", "-m", "skill.benchmark.worker"],
            stderr="ValueError: MiniMaxTextClient requires a non-empty api_key",
        )

    monkeypatch.setattr(harness.subprocess, "run", _failing_subprocess_run)

    record = harness._run_case_fresh_process(
        case=case,
        run_index=1,
        app_import_path="skill.api.entry:app",
    )

    assert record.case_id == "smoke-mixed-01"
    assert record.route_label == "mixed"
    assert record.answer_status == "retrieval_failure"
    assert record.retrieval_status == "failure_gaps"
    assert record.success is False
    assert record.failure_reason == "worker_error"
    assert record.latency_budget_ok is False
    assert record.elapsed_ms == 0
