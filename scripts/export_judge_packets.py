"""Export per-case answer/evidence packets for offline judging."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skill.api.entry import app
from skill.benchmark.harness import load_benchmark_cases
from skill.benchmark.judge_packets import export_judge_packets

_DEFAULT_CASES_PATH = Path("tests/fixtures/benchmark_phase5_cases.json")


def _configure_shadow_eval_environment() -> None:
    os.environ["WASC_RETRIEVAL_MODE"] = "live"
    os.environ["WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED"] = "0"


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
    parser.add_argument(
        "--fresh-process",
        action="store_true",
        help="Export each packet in a dedicated Python process",
    )
    parser.add_argument(
        "--shadow-eval",
        action="store_true",
        help="Align export with benchmark shadow-eval settings (live mode, fixture shortcuts off, fresh-process)",
    )
    parser.add_argument(
        "--app-import-path",
        default="skill.api.entry:app",
        help="Import path for the FastAPI app when using fresh-process export",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.shadow_eval:
        _configure_shadow_eval_environment()
    cases = load_benchmark_cases(args.cases)
    index_payload = export_judge_packets(
        app=app,
        cases=cases,
        cases_path=args.cases,
        output_dir=args.output_dir,
        fresh_process=args.fresh_process or args.shadow_eval,
        app_import_path=args.app_import_path,
    )
    print(f"Exported {index_payload['total_cases']} judge packets to: {args.output_dir}")
    print(f"Index saved to: {args.output_dir / 'judge-packets-index.json'}")
    print(f"ASCII-safe bundle saved to: {args.output_dir / 'judge-bundle-minimal.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
