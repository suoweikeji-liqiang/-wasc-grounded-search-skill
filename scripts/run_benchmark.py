"""User-facing CLI for the Phase 5 benchmark harness."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skill.api.entry import app
from skill.benchmark.harness import load_benchmark_cases, run_benchmark_suite
from skill.benchmark.report import write_benchmark_reports

_DEFAULT_CASES_PATH = Path("tests/fixtures/benchmark_phase5_cases.json")
_SMOKE_CASES_PATH = Path("tests/fixtures/benchmark_hidden_style_smoke_cases.json")


def _configure_shadow_eval_environment() -> None:
    os.environ["WASC_RETRIEVAL_MODE"] = "live"
    os.environ["WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED"] = "0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 5 benchmark suite against the live /answer path."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=_DEFAULT_CASES_PATH,
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
    parser.add_argument(
        "--fresh-process",
        action="store_true",
        help="Run each benchmark attempt in a dedicated Python process",
    )
    parser.add_argument(
        "--smoke-gate",
        action="store_true",
        help="Run the fixed hidden-style live smoke suite in fresh-process mode",
    )
    parser.add_argument(
        "--app-import-path",
        default="skill.api.entry:app",
        help="Import path for the FastAPI app when using --fresh-process",
    )
    return parser.parse_args()


def main() -> None:
    _configure_shadow_eval_environment()
    args = parse_args()
    cases_path = _SMOKE_CASES_PATH if args.smoke_gate else args.cases
    runs = 1 if args.smoke_gate else args.runs
    fresh_process = args.fresh_process or args.smoke_gate
    cases = load_benchmark_cases(cases_path)
    records = run_benchmark_suite(
        app=app,
        cases=cases,
        runs=runs,
        output_dir=args.output_dir,
        fresh_process=fresh_process,
        app_import_path=args.app_import_path,
    )
    write_benchmark_reports(records, args.output_dir)


if __name__ == "__main__":
    main()
