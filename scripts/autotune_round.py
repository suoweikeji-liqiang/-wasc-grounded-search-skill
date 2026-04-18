"""Manage one autotune round and persist its artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skill.autotune.models import BenchmarkSnapshot, DecisionSnapshot, JudgeSnapshot, RoundMetadata
from skill.autotune.rounds import (
    copy_cases_manifest,
    ensure_round_layout,
    load_round_metadata,
    load_rounds,
    render_scoreboard,
    write_json_file,
    write_round_metadata,
)
from skill.benchmark.harness import load_benchmark_cases, run_benchmark_suite
from skill.benchmark.judge_packets import export_judge_packets
from skill.benchmark.judge_score_report import load_judge_scores, summarize_judge_scores
from skill.benchmark.report import write_benchmark_reports

_DEFAULT_OUTPUT_ROOT = Path("benchmark-results") / "autotune"
_DEFAULT_SCOREBOARD_PATH = Path("docs") / "autotune" / "scoreboard.md"


def _configure_shadow_eval_environment() -> None:
    os.environ["WASC_RETRIEVAL_MODE"] = "live"
    os.environ["WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED"] = "0"


def _load_app():
    from skill.api.entry import app

    return app


def _default_git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _grounded_success_from_summary(summary_path: Path) -> float | None:
    if not summary_path.exists():
        return None
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    total_runs = int(payload.get("total_runs", 0))
    if total_runs <= 0:
        return None
    answer_status_breakdown = payload.get("answer_status_breakdown", {})
    grounded_success_runs = int(answer_status_breakdown.get("grounded_success", 0))
    return round(grounded_success_runs / total_runs, 3)


def _judge_aggregate_from_summary(summary: dict[str, Any]) -> float | None:
    cases_payload = summary.get("cases", {})
    if not isinstance(cases_payload, dict) or not cases_payload:
        return None

    ratios: list[float] = []
    for case_payload in cases_payload.values():
        if not isinstance(case_payload, dict):
            continue
        ratio = case_payload.get("total_normalized_ratio")
        if isinstance(ratio, (int, float)):
            ratios.append(float(ratio))

    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 3)


def _load_round_layout_metadata(output_root: Path, round_id: str) -> tuple[RoundMetadata, Path]:
    layout = ensure_round_layout(output_root, round_id)
    metadata = load_round_metadata(layout.round_metadata_path)
    return metadata, layout.round_dir


def _write_scoreboard(output_root: Path, scoreboard_path: Path) -> None:
    rounds = load_rounds(output_root)
    scoreboard_path.parent.mkdir(parents=True, exist_ok=True)
    scoreboard_path.write_text(render_scoreboard(rounds), encoding="utf-8")


def _prepare_round(args: argparse.Namespace) -> int:
    layout = ensure_round_layout(args.output_root, args.round_id)
    copy_cases_manifest(args.cases, layout.cases_path)

    metadata = RoundMetadata(
        round_id=args.round_id,
        hypothesis=args.hypothesis,
        git_sha=args.git_sha,
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
    print(f"Prepared round directory: {layout.round_dir}")
    print(f"Copied cases manifest to: {layout.cases_path}")
    return 0


def _benchmark_round(args: argparse.Namespace) -> int:
    _configure_shadow_eval_environment()
    metadata, _round_dir = _load_round_layout_metadata(args.output_root, args.round_id)
    cases = load_benchmark_cases(metadata.cases_path)
    records = run_benchmark_suite(
        app=None if args.fresh_process else _load_app(),
        cases=cases,
        runs=args.runs,
        output_dir=metadata.benchmark.output_dir,
        fresh_process=args.fresh_process,
        app_import_path=args.app_import_path,
        max_parallel=args.max_parallel,
    )
    write_benchmark_reports(records, metadata.benchmark.output_dir)
    print(f"Wrote benchmark artifacts to: {metadata.benchmark.output_dir}")
    return 0


def _packets_round(args: argparse.Namespace) -> int:
    if args.shadow_eval:
        _configure_shadow_eval_environment()
    metadata, round_dir = _load_round_layout_metadata(args.output_root, args.round_id)
    cases = load_benchmark_cases(metadata.cases_path)
    export_judge_packets(
        app=None if (args.fresh_process or args.shadow_eval) else _load_app(),
        cases=cases,
        cases_path=metadata.cases_path,
        output_dir=round_dir,
        fresh_process=args.fresh_process or args.shadow_eval,
        app_import_path=args.app_import_path,
        max_parallel=args.max_parallel,
    )
    print(f"Wrote judge packets to: {metadata.judge.packet_dir}")
    return 0


def _report_round(args: argparse.Namespace) -> int:
    layout = ensure_round_layout(args.output_root, args.round_id)
    metadata = load_round_metadata(layout.round_metadata_path)

    judge_entries = load_judge_scores(layout.judge_scores_dir)
    judge_summary = summarize_judge_scores(judge_entries)
    write_json_file(layout.judge_summary_path, judge_summary)

    updated_metadata = metadata.model_copy(
        update={
            "benchmark": metadata.benchmark.model_copy(
                update={
                    "grounded_success": _grounded_success_from_summary(metadata.benchmark.summary_path),
                }
            ),
            "judge": metadata.judge.model_copy(
                update={
                    "summary_path": layout.judge_summary_path,
                    "aggregate_score": _judge_aggregate_from_summary(judge_summary),
                    "total_scores": int(judge_summary.get("total_scores", 0)),
                }
            ),
            "decision": DecisionSnapshot(
                outcome=args.decision,
                reason=args.reason,
            ),
        }
    )
    write_round_metadata(layout.round_metadata_path, updated_metadata)
    write_json_file(
        layout.decision_path,
        {
            "round_id": updated_metadata.round_id,
            "outcome": updated_metadata.decision.outcome,
            "reason": updated_metadata.decision.reason,
            "grounded_success": updated_metadata.benchmark.grounded_success,
            "judge_aggregate_score": updated_metadata.judge.aggregate_score,
        },
    )
    _write_scoreboard(args.output_root, args.scoreboard)
    print(f"Wrote judge summary to: {layout.judge_summary_path}")
    print(f"Updated scoreboard at: {args.scoreboard}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage prepare/benchmark/packets/report steps for one autotune round.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Create a round directory and seed metadata.")
    prepare_parser.add_argument("--round-id", required=True)
    prepare_parser.add_argument("--hypothesis", required=True)
    prepare_parser.add_argument("--cases", type=Path, required=True)
    prepare_parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--git-sha", default=None)

    benchmark_parser = subparsers.add_parser("benchmark", help="Run the benchmark harness for a prepared round.")
    benchmark_parser.add_argument("--round-id", required=True)
    benchmark_parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    benchmark_parser.add_argument("--runs", type=int, default=1)
    benchmark_parser.add_argument("--fresh-process", action="store_true")
    benchmark_parser.add_argument("--max-parallel", type=int, default=1)
    benchmark_parser.add_argument("--app-import-path", default="skill.api.entry:app")

    packets_parser = subparsers.add_parser("packets", help="Export judge packets for a prepared round.")
    packets_parser.add_argument("--round-id", required=True)
    packets_parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    packets_parser.add_argument("--fresh-process", action="store_true")
    packets_parser.add_argument("--shadow-eval", action="store_true")
    packets_parser.add_argument("--max-parallel", type=int, default=1)
    packets_parser.add_argument("--app-import-path", default="skill.api.entry:app")

    report_parser = subparsers.add_parser("report", help="Aggregate judge scores and refresh scoreboard.")
    report_parser.add_argument("--round-id", required=True)
    report_parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    report_parser.add_argument("--scoreboard", type=Path, default=_DEFAULT_SCOREBOARD_PATH)
    report_parser.add_argument(
        "--decision",
        choices=("baseline", "kept", "reverted", "rejected"),
        required=True,
    )
    report_parser.add_argument("--reason", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        if args.git_sha is None:
            args.git_sha = _default_git_sha()
        return _prepare_round(args)
    if args.command == "benchmark":
        return _benchmark_round(args)
    if args.command == "packets":
        return _packets_round(args)
    if args.command == "report":
        return _report_round(args)
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
