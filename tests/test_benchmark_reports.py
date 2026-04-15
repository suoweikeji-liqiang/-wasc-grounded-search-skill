"""Phase 5 benchmark report regressions."""

from __future__ import annotations

import csv
import importlib.util
import json
import os
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
            retrieval_trace=[
                {
                    "source_id": "policy_official_registry",
                    "stage": "first_wave",
                    "started_at_ms": 0,
                    "elapsed_ms": 100,
                    "hit_count": 1,
                    "error_class": "ok",
                    "was_cancelled_by_deadline": False,
                }
            ],
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
            retrieval_trace=[],
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
            retrieval_trace=[
                {
                    "source_id": "academic_semantic_scholar",
                    "stage": "first_wave",
                    "started_at_ms": 0,
                    "elapsed_ms": 210,
                    "hit_count": 0,
                    "error_class": "timeout",
                    "was_cancelled_by_deadline": True,
                }
            ],
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
            retrieval_trace=[],
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
    assert jsonl_rows[0]["retrieval_trace"] == [
        {
            "source_id": "policy_official_registry",
            "stage": "first_wave",
            "started_at_ms": 0,
            "elapsed_ms": 100,
            "hit_count": 1,
            "error_class": "ok",
            "was_cancelled_by_deadline": False,
        }
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


def test_run_benchmark_cli_forces_live_shadow_eval(monkeypatch, tmp_path) -> None:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("phase5_run_benchmark", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("WASC_RETRIEVAL_MODE", raising=False)
    monkeypatch.delenv("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_benchmark.py",
            "--cases",
            "tests/fixtures/benchmark_phase5_cases.json",
            "--runs",
            "1",
            "--output-dir",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(module, "load_benchmark_cases", lambda _path: [])

    observed: dict[str, str | None] = {}

    def _fake_run_benchmark_suite(**kwargs: object) -> list[BenchmarkRunRecord]:
        del kwargs
        observed["mode"] = os.environ.get("WASC_RETRIEVAL_MODE")
        observed["fixture_shortcuts"] = os.environ.get("WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED")
        return []

    monkeypatch.setattr(module, "run_benchmark_suite", _fake_run_benchmark_suite)
    monkeypatch.setattr(module, "write_benchmark_reports", lambda records, output_dir: None)

    module.main()

    assert observed == {
        "mode": "live",
        "fixture_shortcuts": "0",
    }


def test_run_benchmark_cli_smoke_gate_uses_hidden_fixture_and_fresh_process(
    monkeypatch,
    tmp_path,
) -> None:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("phase5_run_benchmark_smoke", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_benchmark.py",
            "--smoke-gate",
            "--output-dir",
            str(tmp_path),
        ],
    )

    observed: dict[str, object] = {}

    def _fake_load_benchmark_cases(path: Path) -> list[object]:
        observed["cases_path"] = path
        return []

    monkeypatch.setattr(module, "load_benchmark_cases", _fake_load_benchmark_cases)

    def _fake_run_benchmark_suite(**kwargs: object) -> list[BenchmarkRunRecord]:
        observed["fresh_process"] = kwargs["fresh_process"]
        observed["runs"] = kwargs["runs"]
        observed["app_import_path"] = kwargs["app_import_path"]
        return []

    monkeypatch.setattr(module, "run_benchmark_suite", _fake_run_benchmark_suite)
    monkeypatch.setattr(module, "write_benchmark_reports", lambda records, output_dir: None)

    module.main()

    assert observed == {
        "cases_path": Path("tests/fixtures/benchmark_hidden_style_smoke_cases.json"),
        "fresh_process": True,
        "runs": 1,
        "app_import_path": "skill.api.entry:app",
    }
