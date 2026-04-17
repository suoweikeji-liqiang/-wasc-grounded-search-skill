"""Summarize offline judge score files into one round report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skill.benchmark.judge_score_report import load_judge_scores, summarize_judge_scores


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize judge score JSON files into one round report.",
    )
    parser.add_argument(
        "--scores-dir",
        type=Path,
        required=True,
        help="Directory containing judge score JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the summary JSON file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = load_judge_scores(args.scores_dir)
    summary = summarize_judge_scores(entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"Loaded {summary['total_scores']} judge scores from: {args.scores_dir}")
    print(f"Summary saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
