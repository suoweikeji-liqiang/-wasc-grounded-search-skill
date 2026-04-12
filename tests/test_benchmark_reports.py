"""Phase 5 benchmark report regressions."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

from skill.benchmark.models import BenchmarkRunRecord


def _sample_records() -> list[BenchmarkRunRecord]:
    return [
        BenchmarkRunRecord(
            case_id="policy-01",
            run_index=1,
            query="latest climate order version",
            route_label="policy",
            answer_status="grounded_success",
            retrieval_status="success",
            success=True,
            elapsed_ms=100,
            evidence_token_estimate=20,
            answer_token_estimate=12,
            latency_budget_ok=True,
            token_budget_ok=True,
            failure_reason=None,
        ),
        BenchmarkRunRecord(
            case_id="policy-01",
            run_index=2,
            query="latest climate order version",
            route_label="policy",
            answer_status="insufficient_evidence",
            retrieval_status="partial",
            success=False,
            elapsed_ms=140,
            evidence_token_estimate=22,
            answer_token_estimate=15,
            latency_budget_ok=True,
            token_budget_ok=False,
            failure_reason=None,
        ),
        BenchmarkRunRecord(
            case_id="academic-01",
            run_index=1,
            query="grounded search evidence packing paper",
            route_label="academic",
            answer_status="grounded_success",
            retrieval_status="success",
            success=True,
            elapsed_ms=210,
            evidence_token_estimate=26,
            answer_token_estimate=16,
            latency_budget_ok=False,
            token_budget_ok=True,
            failure_reason="timeout",
        ),
        BenchmarkRunRecord(
            case_id="mixed-01",
            run_index=1,
            query="autonomous driving policy impact on industry",
            route_label="mixed",
            answer_status="retrieval_failure",
            retrieval_status="failure_gaps",
            success=False,
            elapsed_ms=280,
            evidence_token_estimate=8,
            answer_token_estimate=6,
            latency_budget_ok=False,
            token_budget_ok=False,
            failure_reason="adapter_error",
        ),
    ]


def test_summarize_benchmark_runs_derives_metrics_from_raw_records() -> None:
    from skill.benchmark.report import summarize_benchmark_runs

    summary = summarize_benchmark_runs(_sample_records())

    payload = summary.model_dump()
    assert set(payload) == {
        "total_runs",
        "successful_runs",
        "success_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_budget_pass_rate",
        "token_budget_pass_rate",
        "answer_status_breakdown",
        "failure_reason_breakdown",
    }
    assert payload["total_runs"] == 4
    assert payload["successful_runs"] == 2
    assert 0.0 <= payload["success_rate"] <= 1.0
    assert payload["latency_p95_ms"] >= payload["latency_p50_ms"]
    assert payload["answer_status_breakdown"] == {
        "grounded_success": 2,
        "insufficient_evidence": 1,
        "retrieval_failure": 1,
    }
    assert payload["failure_reason_breakdown"] == {
        "timeout": 1,
        "adapter_error": 1,
    }


def test_write_benchmark_reports_writes_expected_files_and_preserves_run_order(
    tmp_path,
) -> None:
    from skill.benchmark.report import write_benchmark_reports

    records = _sample_records()
    write_benchmark_reports(records, tmp_path)

    jsonl_path = tmp_path / "benchmark-runs.jsonl"
    csv_path = tmp_path / "benchmark-runs.csv"
    summary_path = tmp_path / "benchmark-summary.json"

    assert jsonl_path.exists()
    assert csv_path.exists()
    assert summary_path.exists()

    jsonl_rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [(row["case_id"], row["run_index"]) for row in jsonl_rows] == [
        (record.case_id, record.run_index) for record in records
    ]

    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert [(row["case_id"], int(row["run_index"])) for row in csv_rows] == [
        (record.case_id, record.run_index) for record in records
    ]

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert set(summary_payload) == {
        "total_runs",
        "successful_runs",
        "success_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_budget_pass_rate",
        "token_budget_pass_rate",
        "answer_status_breakdown",
        "failure_reason_breakdown",
    }
    assert 0.0 <= summary_payload["success_rate"] <= 1.0
    assert summary_payload["latency_p95_ms"] >= summary_payload["latency_p50_ms"]


def test_run_benchmark_cli_uses_phase_5_defaults(monkeypatch) -> None:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("phase5_run_benchmark", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(sys, "argv", ["run_benchmark.py"])

    args = module.parse_args()

    assert args.cases == Path("tests/fixtures/benchmark_phase5_cases.json")
    assert args.runs == 5
    assert args.output_dir == Path("benchmark-results")
