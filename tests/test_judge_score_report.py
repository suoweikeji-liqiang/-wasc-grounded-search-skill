"""Judge score report regressions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def test_summarize_judge_scores_aggregates_dimension_and_case_metrics() -> None:
    from skill.benchmark.judge_score_report import summarize_judge_scores

    summary = summarize_judge_scores(
        [
            {
                "case_id": "policy-01",
                "dimension": "信息全面度",
                "score": 12,
                "rationale": "partial coverage",
                "positives": ["structured output"],
                "negatives": ["misses one key detail"],
            },
            {
                "case_id": "policy-01",
                "dimension": "信息准确度",
                "score": 18,
                "rationale": "well grounded",
                "positives": ["source-backed"],
                "negatives": [],
            },
            {
                "case_id": "policy-01",
                "dimension": "易用性",
                "score": 7,
                "rationale": "readable enough",
                "positives": ["clear sections"],
                "negatives": ["no next step hint"],
            },
            {
                "case_id": "industry-01",
                "dimension": "信息全面度",
                "score": 4,
                "rationale": "mostly failed",
                "positives": ["failure is clear"],
                "negatives": ["not enough coverage"],
            },
            {
                "case_id": "industry-01",
                "dimension": "信息准确度",
                "score": 20,
                "rationale": "no unsupported claim",
                "positives": ["conservative"],
                "negatives": ["no factual answer"],
            },
            {
                "case_id": "industry-01",
                "dimension": "易用性",
                "score": 5,
                "rationale": "diagnostic but technical",
                "positives": ["explicit failure"],
                "negatives": ["too internal"],
            },
        ]
    )

    assert summary["total_scores"] == 6
    assert summary["dimensions"]["信息全面度"]["average_score"] == 8.0
    assert summary["dimensions"]["信息准确度"]["average_score"] == 19.0
    assert summary["dimensions"]["易用性"]["average_score"] == 6.0
    assert summary["dimensions"]["信息全面度"]["max_score"] == 20
    assert summary["dimensions"]["易用性"]["max_score"] == 10
    assert summary["cases"]["policy-01"]["total_normalized_ratio"] == 0.74
    assert summary["cases"]["industry-01"]["total_normalized_ratio"] == 0.58


def test_summarize_judge_scores_cli_reads_json_files_and_writes_summary(
    tmp_path,
    monkeypatch,
) -> None:
    scores_dir = tmp_path / "judge-scores"
    scores_dir.mkdir()
    (scores_dir / "completeness.json").write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "dimension": "信息全面度",
                    "score": 10,
                    "rationale": "ok",
                    "positives": [],
                    "negatives": [],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (scores_dir / "accuracy.json").write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "dimension": "信息准确度",
                    "score": 19,
                    "rationale": "good",
                    "positives": [],
                    "negatives": [],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (scores_dir / "usability.json").write_text(
        json.dumps(
            {
                "case_id": "policy-01",
                "dimension": "易用性",
                "score": 8,
                "rationale": "clear",
                "positives": [],
                "negatives": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    module_path = Path(__file__).resolve().parent.parent / "scripts" / "summarize_judge_scores.py"
    spec = importlib.util.spec_from_file_location("summarize_judge_scores_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output_path = tmp_path / "judge-score-summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_judge_scores.py",
            "--scores-dir",
            str(scores_dir),
            "--output",
            str(output_path),
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["total_scores"] == 3
    assert payload["dimensions"]["信息全面度"]["average_score"] == 10.0
    assert payload["dimensions"]["信息准确度"]["average_score"] == 19.0
    assert payload["dimensions"]["易用性"]["average_score"] == 8.0
