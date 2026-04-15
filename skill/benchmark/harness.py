"""Repeatable local benchmark runner over the `/answer` path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from skill.benchmark.models import BenchmarkCase, BenchmarkRunRecord
from skill.orchestrator.budget import RuntimeTrace

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Benchmark manifest must be a JSON array")
    return [BenchmarkCase.model_validate(item) for item in payload]


def _record_from_runtime_trace(
    *,
    case: BenchmarkCase,
    run_index: int,
    runtime_trace: RuntimeTrace,
) -> BenchmarkRunRecord:
    return BenchmarkRunRecord(
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
        provider_prompt_tokens=runtime_trace.provider_prompt_tokens,
        provider_completion_tokens=runtime_trace.provider_completion_tokens,
        provider_total_tokens=runtime_trace.provider_total_tokens,
        retrieval_trace=list(runtime_trace.retrieval_trace),
    )


def _run_case_shared_client(
    *,
    client: TestClient,
    app,
    case: BenchmarkCase,
    run_index: int,
) -> BenchmarkRunRecord:
    response = client.post("/answer", json={"query": case.query})
    response.raise_for_status()
    runtime_trace = getattr(app.state, "last_runtime_trace", None)
    if runtime_trace is None:
        raise RuntimeError("Benchmark run did not publish app.state.last_runtime_trace")
    return _record_from_runtime_trace(
        case=case,
        run_index=run_index,
        runtime_trace=runtime_trace,
    )


def _run_case_fresh_process(
    *,
    case: BenchmarkCase,
    run_index: int,
    app_import_path: str,
) -> BenchmarkRunRecord:
    command = [
        sys.executable,
        "-m",
        "skill.benchmark.worker",
        "--app-import-path",
        app_import_path,
        "--case-id",
        case.case_id,
        "--query",
        case.query,
        "--run-index",
        str(run_index),
    ]
    completed = subprocess.run(
        command,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = completed.stdout.strip().splitlines()[-1]
    return BenchmarkRunRecord.model_validate_json(payload)


def run_benchmark_suite(
    *,
    app,
    cases: list[BenchmarkCase],
    runs: int = 5,
    output_dir: Path,
    fresh_process: bool = False,
    app_import_path: str | None = None,
) -> list[BenchmarkRunRecord]:
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[BenchmarkRunRecord] = []
    if fresh_process:
        if not app_import_path:
            raise ValueError("fresh_process benchmark mode requires app_import_path")
        for case in cases:
            for run_index in range(1, runs + 1):
                records.append(
                    _run_case_fresh_process(
                        case=case,
                        run_index=run_index,
                        app_import_path=app_import_path,
                    )
                )
        return records

    with TestClient(app) as client:
        for case in cases:
            for run_index in range(1, runs + 1):
                records.append(
                    _run_case_shared_client(
                        client=client,
                        app=app,
                        case=case,
                        run_index=run_index,
                    )
                )
    return records
