"""User-facing CLI for the Phase 5 benchmark harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from skill.api.entry import app
from skill.benchmark.harness import load_benchmark_cases, run_benchmark_suite
from skill.benchmark.report import write_benchmark_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 5 benchmark suite against the live /answer path."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/fixtures/benchmark_phase5_cases.json"),
        help="Path to the locked benchmark manifest",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="How many repeated runs to execute per case",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark-results"),
        help="Directory for raw run artifacts and summary output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_benchmark_cases(args.cases)
    records = run_benchmark_suite(
        app=app,
        cases=cases,
        runs=args.runs,
        output_dir=args.output_dir,
    )
    write_benchmark_reports(records, args.output_dir)


if __name__ == "__main__":
    main()
