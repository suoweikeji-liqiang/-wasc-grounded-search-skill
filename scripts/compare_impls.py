"""Compare D:\\study\\WASC and D:\\study\\WASC1 on the same locked benchmark cases."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from skill.api.entry import app

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "tests" / "fixtures" / "benchmark_phase5_cases.json"
DEFAULT_OUTPUT = REPO_ROOT / "benchmark-results" / "impl-comparison-summary.json"
DEFAULT_WASC1_ROOT = Path(r"D:\study\WASC1")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the WASC and WASC1 implementations against the same locked benchmark manifest."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to the locked benchmark manifest JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the comparison report JSON file.",
    )
    parser.add_argument(
        "--repo-wasc1",
        type=Path,
        default=DEFAULT_WASC1_ROOT,
        help="Path to the WASC1 repository root.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Compare only the first N cases. Zero means all.",
    )
    parser.add_argument(
        "--impl",
        choices=("both", "wasc", "wasc1"),
        default="both",
        help="Which implementation(s) to run.",
    )
    return parser.parse_args()


def _normalize_secret(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1].strip()
    return normalized


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _normalize_secret(raw_value)


def _load_cases(path: Path, max_cases: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("benchmark manifest must be a JSON array")

    cases: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each benchmark case must be an object")
        case_id = str(item["case_id"])
        query = str(item["query"])
        expected_route = item.get("expected_route")
        if expected_route is not None:
            expected_route = str(expected_route)
        cases.append(
            {
                "case_id": case_id,
                "query": query,
                "expected_route": expected_route,
            }
        )

    if max_cases > 0:
        return cases[:max_cases]
    return cases


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(rows)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "route_accuracy": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0,
            "avg_sources": 0.0,
            "uncertainty_rate": 0.0,
            "non_empty_response_rate": 0.0,
            "grounded_success_rate": None,
            "error_rate": 0.0,
        }

    route_comparable = [
        row for row in rows if row.get("expected_route") is not None and row.get("route_label") is not None
    ]
    route_hits = sum(
        1 for row in route_comparable if row.get("route_label") == row.get("expected_route")
    )
    latencies = [int(row.get("elapsed_ms", 0) or 0) for row in rows]
    source_counts = [int(row.get("sources_count", 0) or 0) for row in rows]
    uncertainty_hits = sum(1 for row in rows if int(row.get("uncertainties_count", 0) or 0) > 0)
    non_empty_hits = sum(1 for row in rows if bool(str(row.get("response_preview", "")).strip()))
    errors = sum(1 for row in rows if row.get("error"))

    grounded_status_rows = [row for row in rows if row.get("answer_status") is not None]
    grounded_success_rate = None
    if grounded_status_rows:
        grounded_successes = sum(
            1 for row in grounded_status_rows if row.get("answer_status") == "grounded_success"
        )
        grounded_success_rate = round(grounded_successes / len(grounded_status_rows), 4)

    return {
        "total_cases": total_cases,
        "route_accuracy": round(
            route_hits / len(route_comparable), 4
        )
        if route_comparable
        else None,
        "avg_latency_ms": round(sum(latencies) / total_cases, 2),
        "p95_latency_ms": _p95(latencies),
        "avg_sources": round(sum(source_counts) / total_cases, 2),
        "uncertainty_rate": round(uncertainty_hits / total_cases, 4),
        "non_empty_response_rate": round(non_empty_hits / total_cases, 4),
        "grounded_success_rate": grounded_success_rate,
        "error_rate": round(errors / total_cases, 4),
    }


def _run_wasc(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _load_env_file(REPO_ROOT / ".env")
    rows: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for case in cases:
            wall_started = perf_counter()
            error: str | None = None
            payload: dict[str, Any] = {}
            route_label: str | None = None
            elapsed_ms: int = 0
            try:
                response = client.post("/answer", json={"query": case["query"]})
                payload = response.json()
                response.raise_for_status()
                runtime_trace = getattr(app.state, "last_runtime_trace", None)
                route_label = payload.get("route_label")
                if runtime_trace is not None:
                    elapsed_ms = int(runtime_trace.elapsed_ms)
                else:
                    elapsed_ms = round((perf_counter() - wall_started) * 1000)
            except Exception as exc:  # pragma: no cover - exercised by live comparison only
                error = f"{type(exc).__name__}: {exc}"
                elapsed_ms = round((perf_counter() - wall_started) * 1000)

            rows.append(
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "expected_route": case.get("expected_route"),
                    "route_label": route_label,
                    "elapsed_ms": elapsed_ms,
                    "sources_count": len(payload.get("sources", [])) if payload else 0,
                    "uncertainties_count": len(payload.get("uncertainty_notes", [])) if payload else 0,
                    "answer_status": payload.get("answer_status") if payload else None,
                    "response_preview": str(payload.get("conclusion", ""))[:240] if payload else "",
                    "error": error,
                }
            )
    return rows


def _run_wasc1(cases: list[dict[str, Any]], repo_wasc1: Path) -> list[dict[str, Any]]:
    helper = r"""
import json
import sys
from pathlib import Path
from time import perf_counter

repo_root = Path(sys.argv[1])
cases = json.loads(sys.stdin.read())
sys.path.insert(0, str(repo_root))

from skill.main import run_query
from skill.router import classify_query

rows = []
for case in cases:
    started = perf_counter()
    error = None
    result = None
    route_label = None
    try:
        route_label = classify_query(case["query"])
        result = run_query(case["query"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result = {
            "summary": "",
            "sources": [],
            "uncertainties": [],
        }
    elapsed_ms = round((perf_counter() - started) * 1000)
    rows.append(
        {
            "case_id": case["case_id"],
            "query": case["query"],
            "expected_route": case.get("expected_route"),
            "route_label": route_label,
            "elapsed_ms": elapsed_ms,
            "sources_count": len(result.get("sources", [])),
            "uncertainties_count": len(result.get("uncertainties", [])),
            "answer_status": None,
            "response_preview": str(result.get("summary", ""))[:240],
            "error": error,
        }
    )

print(json.dumps(rows, ensure_ascii=False))
"""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, "-c", helper, str(repo_wasc1)],
        input=json.dumps(cases, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        text=False,
        cwd=repo_wasc1,
        env=env,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(
            "WASC1 comparison subprocess failed:\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    return json.loads(stdout)


def _print_summary(name: str, summary: dict[str, Any]) -> None:
    print(f"\n{name}")
    print(f"  cases: {summary['total_cases']}")
    print(f"  route_accuracy: {summary['route_accuracy']}")
    print(f"  avg_latency_ms: {summary['avg_latency_ms']}")
    print(f"  p95_latency_ms: {summary['p95_latency_ms']}")
    print(f"  avg_sources: {summary['avg_sources']}")
    print(f"  uncertainty_rate: {summary['uncertainty_rate']}")
    print(f"  non_empty_response_rate: {summary['non_empty_response_rate']}")
    print(f"  grounded_success_rate: {summary['grounded_success_rate']}")
    print(f"  error_rate: {summary['error_rate']}")


def main() -> int:
    args = _parse_args()
    cases = _load_cases(args.dataset, args.max_cases)

    report: dict[str, Any] = {
        "dataset": str(args.dataset),
        "repo_wasc": str(REPO_ROOT),
        "repo_wasc1": str(args.repo_wasc1),
        "cases": cases,
        "results": {},
        "summary": {},
    }

    if args.impl in {"both", "wasc"}:
        wasc_rows = _run_wasc(cases)
        report["results"]["wasc"] = wasc_rows
        report["summary"]["wasc"] = _summarize(wasc_rows)

    if args.impl in {"both", "wasc1"}:
        wasc1_rows = _run_wasc1(cases, args.repo_wasc1)
        report["results"]["wasc1"] = wasc1_rows
        report["summary"]["wasc1"] = _summarize(wasc1_rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output}")
    if "wasc" in report["summary"]:
        _print_summary("WASC", report["summary"]["wasc"])
    if "wasc1" in report["summary"]:
        _print_summary("WASC1", report["summary"]["wasc1"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
