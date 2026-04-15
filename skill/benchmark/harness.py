"""Repeatable local benchmark runner over the `/answer` path."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from skill.benchmark.models import BenchmarkCase, BenchmarkRunRecord


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Benchmark manifest must be a JSON array")
    return [BenchmarkCase.model_validate(item) for item in payload]


def run_benchmark_suite(
    *,
    app,
    cases: list[BenchmarkCase],
    runs: int = 5,
    output_dir: Path,
) -> list[BenchmarkRunRecord]:
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[BenchmarkRunRecord] = []
    with TestClient(app) as client:
        for case in cases:
            for run_index in range(1, runs + 1):
                response = client.post("/answer", json={"query": case.query})
                response.raise_for_status()
                runtime_trace = getattr(app.state, "last_runtime_trace", None)
                if runtime_trace is None:
                    raise RuntimeError("Benchmark run did not publish app.state.last_runtime_trace")

                records.append(
                    BenchmarkRunRecord(
                        case_id=case.case_id,
                        run_index=run_index,
                        query=case.query,
                        route_label=runtime_trace.route_label,
                        answer_status=runtime_trace.answer_status,
                        retrieval_status=runtime_trace.retrieval_status,
                        success=runtime_trace.answer_status == "grounded_success",
                        elapsed_ms=runtime_trace.elapsed_ms,
                        evidence_token_estimate=runtime_trace.evidence_token_estimate,
                        answer_token_estimate=runtime_trace.answer_token_estimate,
                        latency_budget_ok=runtime_trace.latency_budget_ok,
                        token_budget_ok=runtime_trace.token_budget_ok,
                        failure_reason=runtime_trace.failure_reason,
                        retrieval_trace=list(runtime_trace.retrieval_trace),
                    )
                )
    return records
