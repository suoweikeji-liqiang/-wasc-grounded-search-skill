"""Aggregate offline judge scores into round summaries."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


_MAX_SCORE_BY_DIMENSION: dict[str, int] = {
    "信息全面度": 20,
    "信息准确度": 20,
    "易用性": 10,
}


def _normalize_entries(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise ValueError("judge score file must be a JSON object or array of objects")


def load_judge_scores(scores_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(scores_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries.extend(_normalize_entries(payload))
    return entries


def summarize_judge_scores(entries: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cases: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        case_id = str(entry["case_id"])
        dimension = str(entry["dimension"])
        score = float(entry["score"])
        max_score = _MAX_SCORE_BY_DIMENSION.get(dimension)
        if max_score is None:
            raise ValueError(f"unsupported judge dimension: {dimension}")

        normalized_entry = {
            "case_id": case_id,
            "dimension": dimension,
            "score": score,
            "max_score": max_score,
            "rationale": entry.get("rationale", ""),
            "positives": list(entry.get("positives", [])),
            "negatives": list(entry.get("negatives", [])),
        }
        dimensions[dimension].append(normalized_entry)
        cases[case_id].append(normalized_entry)

    dimension_summary: dict[str, dict[str, Any]] = {}
    for dimension, dimension_entries in dimensions.items():
        total_score = sum(item["score"] for item in dimension_entries)
        max_score = dimension_entries[0]["max_score"]
        count = len(dimension_entries)
        dimension_summary[dimension] = {
            "count": count,
            "max_score": max_score,
            "average_score": round(total_score / count, 2) if count else 0.0,
            "average_ratio": round((total_score / (count * max_score)), 2) if count else 0.0,
        }

    case_summary: dict[str, dict[str, Any]] = {}
    for case_id, case_entries in cases.items():
        total_score = sum(item["score"] for item in case_entries)
        total_max = sum(item["max_score"] for item in case_entries)
        case_summary[case_id] = {
            "dimensions": {
                item["dimension"]: {
                    "score": item["score"],
                    "max_score": item["max_score"],
                    "rationale": item["rationale"],
                    "positives": item["positives"],
                    "negatives": item["negatives"],
                }
                for item in case_entries
            },
            "total_score": round(total_score, 2),
            "total_max_score": total_max,
            "total_normalized_ratio": round(total_score / total_max, 2) if total_max else 0.0,
        }

    return {
        "total_scores": len(entries),
        "dimensions": dimension_summary,
        "cases": case_summary,
    }
