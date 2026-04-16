"""Export per-case answer/evidence packets for offline judging."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skill.api.entry import app
from skill.benchmark.harness import load_benchmark_cases
from skill.benchmark.judge_packets import export_judge_packets

_DEFAULT_CASES_PATH = Path("tests/fixtures/benchmark_phase5_cases.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export compact judge packets from /retrieve and /answer.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=_DEFAULT_CASES_PATH,
        help="Path to the benchmark manifest",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark-results") / "judge-packets-round",
        help="Directory where judge packet files will be written",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_benchmark_cases(args.cases)
    index_payload = export_judge_packets(
        app=app,
        cases=cases,
        cases_path=args.cases,
        output_dir=args.output_dir,
    )
    print(f"Exported {index_payload['total_cases']} judge packets to: {args.output_dir}")
    print(f"Index saved to: {args.output_dir / 'judge-packets-index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
