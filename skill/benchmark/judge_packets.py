"""Export compact answer/evidence packets for offline judging."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from skill.benchmark.models import BenchmarkCase
from skill.synthesis.cache import ANSWER_CACHE


_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_JUDGE_BUNDLE_FILENAME = "judge-bundle-minimal.json"


def _safe_filename(value: str) -> str:
    normalized = _SAFE_FILENAME_RE.sub("-", value.strip()).strip("-._")
    return normalized or "case"


def _build_runtime_payload(runtime_trace: object) -> dict[str, Any]:
    return {
        "elapsed_ms": getattr(runtime_trace, "elapsed_ms", 0),
        "retrieval_elapsed_ms": getattr(runtime_trace, "retrieval_elapsed_ms", 0),
        "synthesis_elapsed_ms": getattr(runtime_trace, "synthesis_elapsed_ms", 0),
        "provider_total_tokens": getattr(runtime_trace, "provider_total_tokens", None),
        "failure_reason": getattr(runtime_trace, "failure_reason", None),
        "retrieval_trace": list(getattr(runtime_trace, "retrieval_trace", [])),
    }


def _build_packet(
    *,
    case: BenchmarkCase,
    retrieve_payload: dict[str, Any],
    answer_payload: dict[str, Any],
    runtime_trace: object,
) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "query": case.query,
        "retrieve": {
            "status": retrieve_payload.get("status"),
            "failure_reason": retrieve_payload.get("failure_reason"),
            "gaps": retrieve_payload.get("gaps", []),
            "canonical_evidence": retrieve_payload.get("canonical_evidence", []),
            "evidence_clipped": retrieve_payload.get("evidence_clipped", False),
            "evidence_pruned": retrieve_payload.get("evidence_pruned", False),
        },
        "answer": {
            "answer_status": answer_payload.get("answer_status"),
            "retrieval_status": answer_payload.get("retrieval_status"),
            "conclusion": answer_payload.get("conclusion", ""),
            "key_points": answer_payload.get("key_points", []),
            "sources": answer_payload.get("sources", []),
            "uncertainty_notes": answer_payload.get("uncertainty_notes", []),
            "gaps": answer_payload.get("gaps", []),
        },
        "runtime": _build_runtime_payload(runtime_trace),
    }


def _write_json(path: Path, payload: object, *, ensure_ascii: bool = True) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=ensure_ascii, indent=2),
        encoding="utf-8",
    )


def _build_bundle_payload(
    *,
    packets: list[dict[str, Any]],
    packet_paths: list[str],
    cases_path: Path | None,
) -> dict[str, Any]:
    return {
        "cases_path": None if cases_path is None else str(cases_path),
        "total_cases": len(packets),
        "packet_paths": packet_paths,
        "packets": packets,
    }


def export_judge_packets(
    *,
    app,
    cases: list[BenchmarkCase],
    output_dir: Path,
    cases_path: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_dir = output_dir / "judge-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    ANSWER_CACHE.clear()

    packet_paths: list[str] = []
    packets_index: list[dict[str, Any]] = []
    packets_bundle: list[dict[str, Any]] = []

    with TestClient(app) as client:
        for case in cases:
            answer_response = client.post("/answer", json={"query": case.query})
            answer_response.raise_for_status()
            answer_payload = answer_response.json()

            runtime_trace = getattr(app.state, "last_runtime_trace", None)
            if runtime_trace is None:
                raise RuntimeError("Judge packet export did not publish app.state.last_runtime_trace")
            answer_artifacts = getattr(app.state, "last_answer_artifacts", None)
            if not isinstance(answer_artifacts, dict):
                raise RuntimeError("Judge packet export did not publish app.state.last_answer_artifacts")
            retrieve_payload = answer_artifacts.get("retrieve")
            if not isinstance(retrieve_payload, dict):
                raise RuntimeError("Judge packet export artifacts missing retrieve payload")

            packet = _build_packet(
                case=case,
                retrieve_payload=retrieve_payload,
                answer_payload=answer_payload,
                runtime_trace=runtime_trace,
            )
            packet_filename = f"{_safe_filename(case.case_id)}.json"
            packet_path = packet_dir / packet_filename
            _write_json(packet_path, packet)

            relative_path = str(Path("judge-packets") / packet_filename).replace("\\", "/")
            packet_paths.append(relative_path)
            packets_bundle.append(packet)
            packets_index.append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "packet_path": relative_path,
                    "answer_status": packet["answer"]["answer_status"],
                    "elapsed_ms": packet["runtime"]["elapsed_ms"],
                }
            )

    index_payload = {
        "cases_path": None if cases_path is None else str(cases_path),
        "total_cases": len(cases),
        "packet_paths": packet_paths,
        "packets": packets_index,
    }
    _write_json(output_dir / "judge-packets-index.json", index_payload)
    _write_json(
        output_dir / _JUDGE_BUNDLE_FILENAME,
        _build_bundle_payload(
            packets=packets_bundle,
            packet_paths=packet_paths,
            cases_path=cases_path,
        ),
    )
    return index_payload
