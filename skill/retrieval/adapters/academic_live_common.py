"""Shared ranking helpers for live academic adapters."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from skill.retrieval.priority import score_query_alignment

_MIN_ACADEMIC_LIVE_SCORE = 5
_ACADEMIC_EVIDENCE_PRIORITY: dict[str | None, int] = {
    "peer_reviewed": 3,
    "survey_or_review": 2,
    "preprint": 1,
    "metadata_only": 0,
    None: 0,
}


def _coerce_year(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalize_record(item: dict[str, Any]) -> dict[str, Any] | None:
    title = item.get("title")
    url = item.get("url")
    if not title or not url:
        return None
    snippet = item.get("snippet") or title
    evidence_level = item.get("evidence_level")
    return {
        "title": str(title),
        "url": str(url),
        "snippet": str(snippet),
        "doi": str(item["doi"]) if item.get("doi") is not None else None,
        "arxiv_id": str(item["arxiv_id"]) if item.get("arxiv_id") is not None else None,
        "first_author": str(item["first_author"]) if item.get("first_author") is not None else None,
        "year": _coerce_year(item.get("year")),
        "evidence_level": str(evidence_level) if evidence_level is not None else None,
    }


def academic_alignment_score(query: str, record: dict[str, Any]) -> int:
    return score_query_alignment(
        query,
        route="academic",
        title=str(record["title"]),
        snippet=str(record["snippet"]),
        url=str(record["url"]),
        year=_coerce_year(record.get("year")),
    )


def rank_live_academic_records(
    *,
    query: str,
    records: Iterable[dict[str, Any]],
    max_results: int = 5,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in records:
        normalized = _normalize_record(item)
        if normalized is None:
            continue
        alignment_score = academic_alignment_score(query, normalized)
        if alignment_score < _MIN_ACADEMIC_LIVE_SCORE:
            continue
        ranked.append(
            {
                **normalized,
                "_score": alignment_score,
                "_evidence_priority": _ACADEMIC_EVIDENCE_PRIORITY.get(
                    normalized["evidence_level"],
                    0,
                ),
            }
        )

    ranked.sort(
        key=lambda item: (
            item["_score"],
            item["_evidence_priority"],
            item["year"] or 0,
            item["url"],
        ),
        reverse=True,
    )
    return ranked[: max(1, max_results)]
