"""Aggregate offline judge scores into round summaries."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


_DIMENSION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "completeness": {
        "display_name": "信息全面度",
        "max_score": 20,
        "aliases": ("completeness", "信息全面度"),
    },
    "accuracy": {
        "display_name": "信息准确度",
        "max_score": 20,
        "aliases": ("accuracy", "信息准确度"),
    },
    "usability": {
        "display_name": "易用性",
        "max_score": 10,
        "aliases": ("usability", "易用性"),
    },
}
_DIMENSION_ALIAS_TO_ID: dict[str, str] = {}
for _dimension_id, _definition in _DIMENSION_DEFINITIONS.items():
    for _alias in _definition["aliases"]:
        _DIMENSION_ALIAS_TO_ID[str(_alias).strip().lower()] = _dimension_id


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


def _normalize_dimension(raw_dimension: object) -> str:
    dimension = str(raw_dimension).strip()
    dimension_id = _DIMENSION_ALIAS_TO_ID.get(dimension.lower())
    if dimension_id is None:
        raise ValueError(f"unsupported judge dimension: {dimension}")
    return dimension_id


def summarize_judge_scores(entries: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cases: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        case_id = str(entry["case_id"])
        dimension = _normalize_dimension(entry["dimension"])
        score = float(entry["score"])
        definition = _DIMENSION_DEFINITIONS[dimension]
        max_score = int(definition["max_score"])

        normalized_entry = {
            "case_id": case_id,
            "dimension": dimension,
            "dimension_display_name": definition["display_name"],
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
            "display_name": _DIMENSION_DEFINITIONS[dimension]["display_name"],
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
                    "display_name": item["dimension_display_name"],
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
