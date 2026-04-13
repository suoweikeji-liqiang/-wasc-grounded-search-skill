"""Run the current WASC implementation against WASC1's 12-case competition-eval dataset."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from skill.api.entry import app

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = Path(r"D:\study\WASC1\ref\competition_eval_cases.json")
DEFAULT_OUTPUT = REPO_ROOT / "benchmark-results" / "wasc-on-wasc1-eval-report.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the current WASC implementation against WASC1's competition-eval dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to WASC1 competition_eval_cases.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON report.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Evaluate only the first N cases. Zero means all.",
    )
    parser.add_argument(
        "--print-cases",
        action="store_true",
        help="Print a one-line summary for each case.",
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


def _normalize_expected_terms(raw_terms: Any) -> list[str]:
    if raw_terms is None:
        return []
    if not isinstance(raw_terms, list):
        raise ValueError("expected_terms must be list[str]")
    normalized: list[str] = []
    seen: set[str] = set()
    for term in raw_terms:
        if not isinstance(term, str):
            raise ValueError("expected_terms must be list[str]")
        cleaned = term.strip()
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)
    return normalized


def _load_cases(path: Path, max_cases: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset root must be list")

    cases: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError("each case must be object")

        raw_query = item.get("query")
        if not isinstance(raw_query, str) or not raw_query.strip():
            raise ValueError("query must be non-empty string")

        case_id = str(item.get("id") or f"case-{index}")
        expected_terms = _normalize_expected_terms(item.get("expected_terms"))
        cases.append(
            {
                "id": case_id,
                "query": raw_query.strip(),
                "expected_intent": item.get("expected_intent"),
                "expected_terms": expected_terms,
                "min_sources": int(item.get("min_sources", 1)),
                "max_latency_ms": float(item.get("max_latency_ms", 8000)),
                "min_keyword_coverage": float(
                    item.get("min_keyword_coverage", 0.0 if not expected_terms else 0.5)
                ),
                "require_low_uncertainty": bool(item.get("require_low_uncertainty", False)),
            }
        )

    if max_cases > 0:
        return cases[:max_cases]
    return cases


def _keyword_coverage(expected_terms: list[str], text: str) -> float | None:
    if not expected_terms:
        return None
    lowered = text.lower()
    hits = sum(1 for term in expected_terms if term.lower() in lowered)
    return hits / len(expected_terms)


def _extract_key_point_statements(payload: dict[str, Any]) -> list[str]:
    key_points = payload.get("key_points", [])
    if not isinstance(key_points, list):
        return []
    statements: list[str] = []
    for item in key_points:
        if not isinstance(item, dict):
            continue
        statement = item.get("statement")
        if isinstance(statement, str) and statement.strip():
            statements.append(statement.strip())
    return statements


def _extract_sources(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        return []
    sources: list[dict[str, str]] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if isinstance(title, str) and isinstance(url, str):
            sources.append({"title": title, "url": url})
    return sources


def _extract_uncertainties(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("uncertainty_notes", [])
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
    return items


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    error: str | None = None
    payload: dict[str, Any] = {}

    with TestClient(app) as client:
        try:
            response = client.post("/answer", json={"query": case["query"]})
            payload = response.json()
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - live evaluation path
            error = f"{type(exc).__name__}: {exc}"
            payload = {}

    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    route_label = payload.get("route_label") if payload else None
    conclusion = str(payload.get("conclusion", "")).strip()
    key_points = _extract_key_point_statements(payload)
    sources = _extract_sources(payload)
    uncertainties = _extract_uncertainties(payload)
    source_text_parts = [
        " ".join([source.get("title", ""), source.get("url", "")]).strip()
        for source in sources
    ]
    merged_text = " ".join([conclusion, *key_points, *source_text_parts])
    coverage = _keyword_coverage(case["expected_terms"], merged_text)

    failed_checks: list[str] = []
    if len(sources) < case["min_sources"]:
        failed_checks.append("sources")
    if elapsed_ms > case["max_latency_ms"]:
        failed_checks.append("latency")
    if coverage is not None and coverage < case["min_keyword_coverage"]:
        failed_checks.append("keywords")
    if case["require_low_uncertainty"] and uncertainties:
        failed_checks.append("uncertainty")
    expected_intent = case["expected_intent"]
    intent_match = None if expected_intent is None else route_label == expected_intent
    if intent_match is False:
        failed_checks.append("intent")
    if error:
        failed_checks.append("error")

    return {
        "id": case["id"],
        "query": case["query"],
        "passed": not failed_checks,
        "failed_checks": failed_checks,
        "elapsed_ms": elapsed_ms,
        "summary": conclusion,
        "sources_count": len(sources),
        "uncertainties_count": len(uncertainties),
        "intent_predicted": route_label,
        "intent_match": intent_match,
        "keyword_coverage": coverage,
        "answer_status": payload.get("answer_status") if payload else None,
        "response_preview": conclusion[:240],
        "error": error,
    }


def _safe_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(ordered[index], 2)


def summarize_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "pass_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "avg_sources": 0.0,
            "uncertainty_rate": 0.0,
            "intent_accuracy": None,
            "avg_keyword_coverage": None,
        }

    total_cases = len(reports)
    passed_cases = sum(1 for item in reports if item["passed"])
    latencies = [float(item["elapsed_ms"]) for item in reports]
    source_values = [float(item["sources_count"]) for item in reports]
    uncertain_cases = sum(1 for item in reports if int(item["uncertainties_count"]) > 0)

    intent_values: list[float] = []
    for item in reports:
        value = item["intent_match"]
        if value is None:
            continue
        intent_values.append(1.0 if value else 0.0)

    coverages: list[float] = []
    for item in reports:
        coverage = item["keyword_coverage"]
        if coverage is None:
            continue
        coverages.append(float(coverage))

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "pass_rate": round(passed_cases / total_cases, 4),
        "avg_latency_ms": _safe_avg(latencies),
        "p95_latency_ms": _p95(latencies),
        "avg_sources": _safe_avg(source_values),
        "uncertainty_rate": round(uncertain_cases / total_cases, 4),
        "intent_accuracy": round(sum(intent_values) / len(intent_values), 4) if intent_values else None,
        "avg_keyword_coverage": round(sum(coverages) / len(coverages), 4) if coverages else None,
    }


def main() -> int:
    args = _parse_args()
    _load_env_file(REPO_ROOT / ".env")
    cases = _load_cases(args.dataset, args.max_cases)
    reports = [evaluate_case(case) for case in cases]
    summary = summarize_reports(reports)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(args.dataset),
        "summary": summary,
        "cases": reports,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dataset: {args.dataset}")
    print(f"Cases: {summary['total_cases']}")
    print(f"Passed: {summary['passed_cases']} ({summary['pass_rate']:.2%})")
    print(f"Avg latency: {summary['avg_latency_ms']} ms")
    print(f"P95 latency: {summary['p95_latency_ms']} ms")
    print(f"Avg sources: {summary['avg_sources']}")
    print(f"Uncertainty rate: {summary['uncertainty_rate']:.2%}")
    if summary["intent_accuracy"] is not None:
        print(f"Intent accuracy: {summary['intent_accuracy']:.2%}")
    if summary["avg_keyword_coverage"] is not None:
        print(f"Keyword coverage: {summary['avg_keyword_coverage']:.2%}")
    if args.print_cases:
        for case_report in reports:
            status = "PASS" if case_report["passed"] else "FAIL"
            print(
                f"[{status}] {case_report['id']} {case_report['elapsed_ms']}ms "
                f"checks={case_report['failed_checks']} query={case_report['query']}"
            )
    print(f"Report saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
