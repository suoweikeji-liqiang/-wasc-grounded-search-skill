"""Autotune CLI regressions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from skill.autotune.models import BenchmarkSnapshot, DecisionSnapshot, JudgeSnapshot, RoundMetadata
from skill.autotune.rounds import ensure_round_layout, write_round_metadata


def _load_module() -> object:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "autotune_round.py"
    spec = importlib.util.spec_from_file_location("autotune_round_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_autotune_prepare_creates_round_dir_copies_manifest_and_writes_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "benchmark-results" / "autotune"
    cases_path = tmp_path / "fresh-cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "query": "latest climate order version",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autotune_round.py",
            "prepare",
            "--round-id",
            "baseline-001",
            "--hypothesis",
            "Establish baseline on fresh holdout",
            "--cases",
            str(cases_path),
            "--output-root",
            str(output_root),
            "--git-sha",
            "abc1234",
        ],
    )

    exit_code = module.main()

    round_dir = output_root / "baseline-001"
    copied_cases_path = round_dir / "cases.json"
    metadata_path = round_dir / "round-metadata.json"
    assert exit_code == 0
    assert round_dir.exists()
    assert copied_cases_path.exists()
    assert json.loads(copied_cases_path.read_text(encoding="utf-8")) == json.loads(
        cases_path.read_text(encoding="utf-8")
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["round_id"] == "baseline-001"
    assert metadata["hypothesis"] == "Establish baseline on fresh holdout"
    assert metadata["git_sha"] == "abc1234"
    assert metadata["cases_path"].endswith("baseline-001/cases.json")
    assert metadata["decision"]["outcome"] == "pending"


def test_autotune_benchmark_forwards_max_parallel_to_run_benchmark_suite(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "benchmark-results" / "autotune"
    layout = ensure_round_layout(output_root, "round-010")
    metadata = RoundMetadata(
        round_id="round-010",
        hypothesis="Parallelize fresh-process benchmark workers",
        git_sha="abc1234",
        cases_path=layout.cases_path,
        benchmark=BenchmarkSnapshot(
            output_dir=layout.benchmark_dir,
            summary_path=layout.benchmark_dir / "benchmark-summary.json",
            grounded_success=None,
        ),
        judge=JudgeSnapshot(
            packet_dir=layout.judge_packets_dir,
            scores_dir=layout.judge_scores_dir,
            summary_path=layout.judge_summary_path,
            aggregate_score=None,
            total_scores=0,
        ),
        decision=DecisionSnapshot(outcome="pending", reason=""),
    )
    write_round_metadata(layout.round_metadata_path, metadata)
    layout.cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "query": "latest climate order version",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    def _fake_run_benchmark_suite(**kwargs: object) -> list[object]:
        observed.update(kwargs)
        return []

    monkeypatch.setattr(module, "run_benchmark_suite", _fake_run_benchmark_suite)
    monkeypatch.setattr(module, "write_benchmark_reports", lambda records, output_dir: None)
    monkeypatch.setattr(module, "_load_app", lambda: "fake-app")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autotune_round.py",
            "benchmark",
            "--round-id",
            "round-010",
            "--output-root",
            str(output_root),
            "--runs",
            "2",
            "--fresh-process",
            "--max-parallel",
            "4",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert observed["runs"] == 2
    assert observed["fresh_process"] is True
    assert observed["max_parallel"] == 4
    assert observed["app_import_path"] == "skill.api.entry:app"


def test_autotune_packets_forwards_max_parallel_to_export_judge_packets(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "benchmark-results" / "autotune"
    layout = ensure_round_layout(output_root, "round-011")
    metadata = RoundMetadata(
        round_id="round-011",
        hypothesis="Parallelize fresh-process judge packet export",
        git_sha="abc1234",
        cases_path=layout.cases_path,
        benchmark=BenchmarkSnapshot(
            output_dir=layout.benchmark_dir,
            summary_path=layout.benchmark_dir / "benchmark-summary.json",
            grounded_success=None,
        ),
        judge=JudgeSnapshot(
            packet_dir=layout.judge_packets_dir,
            scores_dir=layout.judge_scores_dir,
            summary_path=layout.judge_summary_path,
            aggregate_score=None,
            total_scores=0,
        ),
        decision=DecisionSnapshot(outcome="pending", reason=""),
    )
    write_round_metadata(layout.round_metadata_path, metadata)
    layout.cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "query": "latest climate order version",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    def _fake_export_judge_packets(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return {"total_cases": 1, "packet_paths": [], "packets": []}

    monkeypatch.setattr(module, "export_judge_packets", _fake_export_judge_packets)
    monkeypatch.setattr(module, "_load_app", lambda: "fake-app")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autotune_round.py",
            "packets",
            "--round-id",
            "round-011",
            "--output-root",
            str(output_root),
            "--fresh-process",
            "--max-parallel",
            "5",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert observed["fresh_process"] is True
    assert observed["max_parallel"] == 5
    assert observed["app_import_path"] == "skill.api.entry:app"


def test_autotune_report_loads_judge_scores_writes_summary_and_updates_scoreboard(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "benchmark-results" / "autotune"
    scoreboard_path = tmp_path / "docs" / "autotune" / "scoreboard.md"
    layout = ensure_round_layout(output_root, "round-002")
    metadata = RoundMetadata(
        round_id="round-002",
        hypothesis="Narrow academic fallback for fresher citations",
        git_sha="abc1234",
        cases_path=layout.cases_path,
        benchmark=BenchmarkSnapshot(
            output_dir=layout.benchmark_dir,
            summary_path=layout.benchmark_dir / "benchmark-summary.json",
            grounded_success=None,
        ),
        judge=JudgeSnapshot(
            packet_dir=layout.judge_packets_dir,
            scores_dir=layout.judge_scores_dir,
            summary_path=layout.judge_summary_path,
            aggregate_score=None,
            total_scores=0,
        ),
        decision=DecisionSnapshot(outcome="pending", reason=""),
    )
    write_round_metadata(layout.round_metadata_path, metadata)
    layout.cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "query": "latest climate order version",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (layout.benchmark_dir / "benchmark-summary.json").write_text(
        json.dumps(
            {
                "total_runs": 4,
                "successful_runs": 3,
                "success_rate": 0.75,
                "latency_p50_ms": 100,
                "latency_p95_ms": 120,
                "latency_budget_pass_rate": 1.0,
                "token_budget_pass_rate": 1.0,
                "answer_status_breakdown": {
                    "grounded_success": 3,
                    "insufficient_evidence": 1,
                },
                "failure_reason_breakdown": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (layout.judge_scores_dir / "judge-1.json").write_text(
        json.dumps(
            {
                "case_id": "policy-01",
                "dimension": "completeness",
                "score": 15,
                "rationale": "covers the main policy details",
                "positives": ["clear structure"],
                "negatives": ["misses one caveat"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (layout.judge_scores_dir / "judge-2.json").write_text(
        json.dumps(
            {
                "case_id": "policy-01",
                "dimension": "accuracy",
                "score": 19,
                "rationale": "well grounded",
                "positives": ["direct citation"],
                "negatives": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (layout.judge_scores_dir / "judge-3.json").write_text(
        json.dumps(
            {
                "case_id": "policy-01",
                "dimension": "usability",
                "score": 8,
                "rationale": "readable and actionable",
                "positives": ["concise summary"],
                "negatives": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autotune_round.py",
            "report",
            "--round-id",
            "round-002",
            "--output-root",
            str(output_root),
            "--scoreboard",
            str(scoreboard_path),
            "--decision",
            "kept",
            "--reason",
            "judge aggregate improved and grounded_success held",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    summary_payload = json.loads(layout.judge_summary_path.read_text(encoding="utf-8"))
    assert summary_payload["total_scores"] == 3
    assert summary_payload["dimensions"]["completeness"]["average_score"] == 15.0
    assert summary_payload["dimensions"]["accuracy"]["average_score"] == 19.0
    assert summary_payload["dimensions"]["usability"]["average_score"] == 8.0

    metadata_payload = json.loads(layout.round_metadata_path.read_text(encoding="utf-8"))
    assert metadata_payload["benchmark"]["grounded_success"] == 0.75
    assert metadata_payload["judge"]["aggregate_score"] == 0.84
    assert metadata_payload["judge"]["total_scores"] == 3
    assert metadata_payload["decision"]["outcome"] == "kept"

    decision_payload = json.loads((layout.round_dir / "decision.json").read_text(encoding="utf-8"))
    assert decision_payload["outcome"] == "kept"
    assert scoreboard_path.exists()
    scoreboard_text = scoreboard_path.read_text(encoding="utf-8")
    assert "| round-002 | Narrow academic fallback for fresher citations | 0.750 | 0.840 | +0.000 | +0.000 | kept |" in scoreboard_text
