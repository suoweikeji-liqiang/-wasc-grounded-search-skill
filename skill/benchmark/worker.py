"""Single-run fresh-process benchmark worker."""

from __future__ import annotations

import argparse
import importlib

from fastapi.testclient import TestClient

from skill.benchmark.harness import _record_from_runtime_trace
from skill.benchmark.models import BenchmarkCase


def _load_app(import_path: str):
    module_name, separator, attr_name = import_path.partition(":")
    if not separator or not module_name or not attr_name:
        raise ValueError("app_import_path must look like 'package.module:app'")
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one benchmark case in a fresh process.")
    parser.add_argument("--app-import-path", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--run-index", required=True, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = _load_app(args.app_import_path)
    case = BenchmarkCase(case_id=args.case_id, query=args.query)
    with TestClient(app) as client:
        response = client.post("/answer", json={"query": case.query})
        response.raise_for_status()
    runtime_trace = getattr(app.state, "last_runtime_trace", None)
    if runtime_trace is None:
        raise RuntimeError("Benchmark worker did not publish app.state.last_runtime_trace")

    record = _record_from_runtime_trace(
        case=case,
        run_index=args.run_index,
        runtime_trace=runtime_trace,
    )
    print(record.model_dump_json())


if __name__ == "__main__":
    main()
