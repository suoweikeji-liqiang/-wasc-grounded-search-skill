"""Autotune round metadata and scoreboard regressions."""

from __future__ import annotations

import json
from pathlib import Path

from skill.autotune.models import (
    BenchmarkSnapshot,
    DecisionSnapshot,
    JudgeSnapshot,
    RoundMetadata,
)
from skill.autotune.rounds import ensure_round_layout, load_round_metadata, render_scoreboard, write_round_metadata


def _round_metadata(*, round_id: str, hypothesis: str, round_dir: Path, grounded_success: float, judge_score: float, decision: str) -> RoundMetadata:
    return RoundMetadata(
        round_id=round_id,
        hypothesis=hypothesis,
        git_sha="abc1234",
        cases_path=round_dir / "cases.json",
        benchmark=BenchmarkSnapshot(
            output_dir=round_dir / "benchmark",
            summary_path=round_dir / "benchmark" / "benchmark-summary.json",
            grounded_success=grounded_success,
        ),
        judge=JudgeSnapshot(
            packet_dir=round_dir / "judge-packets",
            scores_dir=round_dir / "judge-scores",
            summary_path=round_dir / "judge-summary.json",
            aggregate_score=judge_score,
            total_scores=12,
        ),
        decision=DecisionSnapshot(
            outcome=decision,
            reason="judge aggregate improved and grounded_success held",
        ),
    )


def test_round_metadata_serialization_includes_paths_and_decision(tmp_path) -> None:
    layout = ensure_round_layout(tmp_path / "autotune", "round-001")
    metadata = _round_metadata(
        round_id="round-001",
        hypothesis="Tighten evidence packing for policy answers",
        round_dir=layout.round_dir,
        grounded_success=0.58,
        judge_score=0.66,
        decision="kept",
    )

    assert layout.round_dir.exists()
    assert layout.benchmark_dir.exists()
    assert layout.judge_packets_dir.exists()
    assert layout.judge_scores_dir.exists()

    write_round_metadata(layout.round_metadata_path, metadata)

    payload = json.loads(layout.round_metadata_path.read_text(encoding="utf-8"))
    assert payload["round_id"] == "round-001"
    assert payload["hypothesis"] == "Tighten evidence packing for policy answers"
    assert payload["git_sha"] == "abc1234"
    assert payload["cases_path"].endswith("round-001/cases.json")
    assert payload["benchmark"]["output_dir"].endswith("round-001/benchmark")
    assert payload["benchmark"]["summary_path"].endswith("round-001/benchmark/benchmark-summary.json")
    assert payload["judge"]["packet_dir"].endswith("round-001/judge-packets")
    assert payload["judge"]["scores_dir"].endswith("round-001/judge-scores")
    assert payload["judge"]["summary_path"].endswith("round-001/judge-summary.json")
    assert payload["decision"]["outcome"] == "kept"

    loaded = load_round_metadata(layout.round_metadata_path)
    assert loaded.model_dump(mode="json") == metadata.model_dump(mode="json")


def test_render_scoreboard_shows_benchmark_and_judge_deltas(tmp_path) -> None:
    baseline_dir = tmp_path / "autotune" / "baseline-001"
    improved_dir = tmp_path / "autotune" / "round-002"
    baseline = _round_metadata(
        round_id="baseline-001",
        hypothesis="Establish baseline on fresh holdout",
        round_dir=baseline_dir,
        grounded_success=0.54,
        judge_score=0.61,
        decision="baseline",
    )
    improved = _round_metadata(
        round_id="round-002",
        hypothesis="Narrow academic fallback for fresher citations",
        round_dir=improved_dir,
        grounded_success=0.58,
        judge_score=0.68,
        decision="kept",
    )

    markdown = render_scoreboard([baseline, improved])

    assert "| Round | Hypothesis | Grounded Success | Judge Score | Benchmark Delta | Judge Delta | Decision |" in markdown
    assert "| baseline-001 | Establish baseline on fresh holdout | 0.540 | 0.610 | +0.000 | +0.000 | baseline |" in markdown
    assert "| round-002 | Narrow academic fallback for fresher citations | 0.580 | 0.680 | +0.040 | +0.070 | kept |" in markdown
