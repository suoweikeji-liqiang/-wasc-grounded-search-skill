"""Aggregate benchmark report generation."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

from skill.benchmark.models import BenchmarkRunRecord, BenchmarkSummary


def _percentile_nearest_rank(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_benchmark_runs(records: list[BenchmarkRunRecord]) -> BenchmarkSummary:
    total_runs = len(records)
    successful_runs = sum(1 for record in records if record.success)
    latencies = [record.elapsed_ms for record in records]
    latency_budget_passes = sum(1 for record in records if record.latency_budget_ok)
    token_budget_passes = sum(1 for record in records if record.token_budget_ok)
    answer_status_breakdown = dict(Counter(record.answer_status for record in records))
    failure_reason_breakdown = dict(
        Counter(
            record.failure_reason
            for record in records
            if record.failure_reason is not None
        )
    )

    return BenchmarkSummary(
        total_runs=total_runs,
        successful_runs=successful_runs,
        success_rate=(successful_runs / total_runs) if total_runs else 0.0,
        latency_p50_ms=_percentile_nearest_rank(latencies, 0.50),
        latency_p95_ms=_percentile_nearest_rank(latencies, 0.95),
        latency_budget_pass_rate=(
            latency_budget_passes / total_runs if total_runs else 0.0
        ),
        token_budget_pass_rate=(token_budget_passes / total_runs if total_runs else 0.0),
        answer_status_breakdown=answer_status_breakdown,
        failure_reason_breakdown=failure_reason_breakdown,
    )


def write_benchmark_reports(
    records: list[BenchmarkRunRecord],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "benchmark-runs.jsonl"
    csv_path = output_dir / "benchmark-runs.csv"
    summary_path = output_dir / "benchmark-summary.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False))
            handle.write("\n")

    fieldnames = list(BenchmarkRunRecord.model_fields)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.model_dump())

    summary = summarize_benchmark_runs(records)
    summary_path.write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
