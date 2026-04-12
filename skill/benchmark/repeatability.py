"""Repeatability evaluation over grouped benchmark runs."""

from __future__ import annotations

from collections import defaultdict

from skill.benchmark.models import BenchmarkRunRecord


def evaluate_repeatability(
    records: list[BenchmarkRunRecord],
    *,
    expected_runs_per_case: int = 5,
    max_latency_spread_ms: int = 250,
) -> dict[str, object]:
    grouped: dict[str, list[BenchmarkRunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.case_id].append(record)

    cases: dict[str, dict[str, object]] = {}
    for case_id, case_records in grouped.items():
        run_count = len(case_records)
        distinct_answer_status_count = len(
            {record.answer_status for record in case_records}
        )
        distinct_route_label_count = len(
            {record.route_label for record in case_records}
        )
        latencies = [record.elapsed_ms for record in case_records]
        latency_spread_ms = max(latencies) - min(latencies) if latencies else 0
        latency_budget_pass_rate = (
            sum(1 for record in case_records if record.latency_budget_ok) / run_count
            if run_count
            else 0.0
        )
        token_budget_pass_rate = (
            sum(1 for record in case_records if record.token_budget_ok) / run_count
            if run_count
            else 0.0
        )
        repeatable = (
            run_count == expected_runs_per_case
            and distinct_answer_status_count == 1
            and distinct_route_label_count == 1
            and latency_budget_pass_rate == 1.0
            and token_budget_pass_rate == 1.0
            and latency_spread_ms <= max_latency_spread_ms
        )
        cases[case_id] = {
            "run_count": run_count,
            "distinct_answer_status_count": distinct_answer_status_count,
            "distinct_route_label_count": distinct_route_label_count,
            "latency_spread_ms": latency_spread_ms,
            "latency_budget_pass_rate": latency_budget_pass_rate,
            "token_budget_pass_rate": token_budget_pass_rate,
            "repeatable": repeatable,
        }

    return {
        "expected_runs_per_case": expected_runs_per_case,
        "max_latency_spread_ms": max_latency_spread_ms,
        "all_repeatable": bool(cases) and all(
            case_metrics["repeatable"] for case_metrics in cases.values()
        ),
        "cases": cases,
    }
