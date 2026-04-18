"""Filesystem and reporting helpers for autotune rounds."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from skill.autotune.models import RoundMetadata


@dataclass(frozen=True)
class RoundLayout:
    round_dir: Path
    cases_path: Path
    benchmark_dir: Path
    judge_packets_dir: Path
    judge_scores_dir: Path
    round_metadata_path: Path
    judge_summary_path: Path
    decision_path: Path


def _json_ready(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def ensure_round_layout(output_root: Path, round_id: str) -> RoundLayout:
    round_dir = output_root / round_id
    benchmark_dir = round_dir / "benchmark"
    judge_packets_dir = round_dir / "judge-packets"
    judge_scores_dir = round_dir / "judge-scores"

    for path in (round_dir, benchmark_dir, judge_packets_dir, judge_scores_dir):
        path.mkdir(parents=True, exist_ok=True)

    return RoundLayout(
        round_dir=round_dir,
        cases_path=round_dir / "cases.json",
        benchmark_dir=benchmark_dir,
        judge_packets_dir=judge_packets_dir,
        judge_scores_dir=judge_scores_dir,
        round_metadata_path=round_dir / "round-metadata.json",
        judge_summary_path=round_dir / "judge-summary.json",
        decision_path=round_dir / "decision.json",
    )


def write_round_metadata(path: Path, metadata: RoundMetadata) -> None:
    write_json_file(path, metadata.model_dump(mode="python"))


def write_json_file(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def load_round_metadata(path: Path) -> RoundMetadata:
    return RoundMetadata.model_validate_json(path.read_text(encoding="utf-8"))


def load_rounds(output_root: Path) -> list[RoundMetadata]:
    rounds: list[RoundMetadata] = []
    for metadata_path in sorted(output_root.glob("*/round-metadata.json")):
        rounds.append(load_round_metadata(metadata_path))
    return rounds


def copy_cases_manifest(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)


def _format_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def _format_delta(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.3f}"


def render_scoreboard(rounds: Sequence[RoundMetadata]) -> str:
    lines = [
        "# Autotune Scoreboard",
        "",
        "This table tracks benchmark and judge movement for each preserved autotune round.",
        "",
        "| Round | Hypothesis | Grounded Success | Judge Score | Benchmark Delta | Judge Delta | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    best_benchmark: float | None = None
    best_judge: float | None = None

    for round_metadata in rounds:
        benchmark_score = round_metadata.benchmark.grounded_success
        judge_score = round_metadata.judge.aggregate_score

        benchmark_delta = 0.0 if best_benchmark is None and benchmark_score is not None else None
        if best_benchmark is not None and benchmark_score is not None:
            benchmark_delta = benchmark_score - best_benchmark

        judge_delta = 0.0 if best_judge is None and judge_score is not None else None
        if best_judge is not None and judge_score is not None:
            judge_delta = judge_score - best_judge

        lines.append(
            "| {round_id} | {hypothesis} | {benchmark_score} | {judge_score} | {benchmark_delta} | {judge_delta} | {decision} |".format(
                round_id=round_metadata.round_id,
                hypothesis=round_metadata.hypothesis,
                benchmark_score=_format_score(benchmark_score),
                judge_score=_format_score(judge_score),
                benchmark_delta=_format_delta(benchmark_delta),
                judge_delta=_format_delta(judge_delta),
                decision=round_metadata.decision.outcome,
            )
        )

        if round_metadata.decision.outcome in {"baseline", "kept"}:
            if benchmark_score is not None:
                best_benchmark = benchmark_score if best_benchmark is None else max(best_benchmark, benchmark_score)
            if judge_score is not None:
                best_judge = judge_score if best_judge is None else max(best_judge, judge_score)

    lines.append("")
    return "\n".join(lines)
