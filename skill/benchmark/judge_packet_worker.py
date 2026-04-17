"""Single-case fresh-process worker for judge packet export."""

from __future__ import annotations

import argparse
import importlib
import json

from fastapi.testclient import TestClient

from skill.benchmark.judge_packets import _build_packet
from skill.benchmark.models import BenchmarkCase


def _load_app(import_path: str):
    module_name, separator, attr_name = import_path.partition(":")
    if not separator or not module_name or not attr_name:
        raise ValueError("app_import_path must look like 'package.module:app'")
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one judge-packet case in a fresh process.")
    parser.add_argument("--app-import-path", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--query", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = _load_app(args.app_import_path)
    case = BenchmarkCase(case_id=args.case_id, query=args.query)
    with TestClient(app) as client:
        answer_response = client.post("/answer", json={"query": case.query})
        answer_response.raise_for_status()
        answer_payload = answer_response.json()

    runtime_trace = getattr(app.state, "last_runtime_trace", None)
    if runtime_trace is None:
        raise RuntimeError("Judge packet worker did not publish app.state.last_runtime_trace")
    answer_artifacts = getattr(app.state, "last_answer_artifacts", None)
    if not isinstance(answer_artifacts, dict):
        raise RuntimeError("Judge packet worker did not publish app.state.last_answer_artifacts")
    retrieve_payload = answer_artifacts.get("retrieve")
    if not isinstance(retrieve_payload, dict):
        raise RuntimeError("Judge packet worker artifacts missing retrieve payload")

    packet = _build_packet(
        case=case,
        retrieve_payload=retrieve_payload,
        answer_payload=answer_payload,
        runtime_trace=runtime_trace,
    )
    print(json.dumps(packet))


if __name__ == "__main__":
    main()
