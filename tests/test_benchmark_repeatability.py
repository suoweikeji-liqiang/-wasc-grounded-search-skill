"""Phase 5 benchmark repeatability regressions."""

from __future__ import annotations

from skill.benchmark.models import BenchmarkRunRecord


def _record(
    *,
    case_id: str,
    run_index: int,
    answer_status: str = "grounded_success",
    route_label: str = "policy",
    elapsed_ms: int = 100,
    latency_budget_ok: bool = True,
    token_budget_ok: bool = True,
) -> BenchmarkRunRecord:
    return BenchmarkRunRecord(
        case_id=case_id,
        run_index=run_index,
        query=f"query-{case_id}",
        route_label=route_label,
        answer_status=answer_status,
        retrieval_status="success",
        success=answer_status == "grounded_success",
        elapsed_ms=elapsed_ms,
        evidence_token_estimate=20,
        answer_token_estimate=12,
        latency_budget_ok=latency_budget_ok,
        token_budget_ok=token_budget_ok,
        failure_reason=None,
    )


def test_evaluate_repeatability_passes_for_stable_grouped_runs() -> None:
    from skill.benchmark.repeatability import evaluate_repeatability

    records = [
        _record(case_id="policy-01", run_index=1, elapsed_ms=100),
        _record(case_id="policy-01", run_index=2, elapsed_ms=110),
        _record(case_id="policy-01", run_index=3, elapsed_ms=120),
        _record(case_id="policy-01", run_index=4, elapsed_ms=130),
        _record(case_id="policy-01", run_index=5, elapsed_ms=140),
    ]

    result = evaluate_repeatability(records)

    assert result["all_repeatable"] is True
    assert result["cases"]["policy-01"] == {
        "run_count": 5,
        "distinct_answer_status_count": 1,
        "distinct_route_label_count": 1,
        "latency_spread_ms": 40,
        "latency_budget_pass_rate": 1.0,
        "token_budget_pass_rate": 1.0,
        "repeatable": True,
    }


def test_evaluate_repeatability_catches_missing_runs_status_drift_and_latency_spread() -> None:
    from skill.benchmark.repeatability import evaluate_repeatability

    records = [
        _record(case_id="missing-runs", run_index=1, elapsed_ms=100),
        _record(case_id="missing-runs", run_index=2, elapsed_ms=110),
        _record(case_id="missing-runs", run_index=3, elapsed_ms=120),
        _record(case_id="missing-runs", run_index=4, elapsed_ms=130),
        _record(case_id="status-drift", run_index=1, elapsed_ms=100),
        _record(case_id="status-drift", run_index=2, elapsed_ms=110),
        _record(case_id="status-drift", run_index=3, answer_status="insufficient_evidence", elapsed_ms=120),
        _record(case_id="status-drift", run_index=4, elapsed_ms=130),
        _record(case_id="status-drift", run_index=5, elapsed_ms=140),
        _record(case_id="latency-spread", run_index=1, elapsed_ms=100),
        _record(case_id="latency-spread", run_index=2, elapsed_ms=120),
        _record(case_id="latency-spread", run_index=3, elapsed_ms=150),
        _record(case_id="latency-spread", run_index=4, elapsed_ms=410),
        _record(case_id="latency-spread", run_index=5, elapsed_ms=700),
    ]

    result = evaluate_repeatability(records)

    assert result["all_repeatable"] is False
    assert result["cases"]["missing-runs"]["run_count"] == 4
    assert result["cases"]["missing-runs"]["repeatable"] is False
    assert result["cases"]["status-drift"]["distinct_answer_status_count"] == 2
    assert result["cases"]["status-drift"]["repeatable"] is False
    assert result["cases"]["latency-spread"]["latency_spread_ms"] == 600
    assert result["cases"]["latency-spread"]["repeatable"] is False
