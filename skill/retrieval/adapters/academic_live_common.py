"""Shared ranking helpers for live academic adapters."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.retrieval.priority import score_query_alignment

_MIN_ACADEMIC_LIVE_SCORE = 5
_ACADEMIC_EVIDENCE_PRIORITY: dict[str | None, int] = {
    "peer_reviewed": 3,
    "survey_or_review": 2,
    "preprint": 1,
    "metadata_only": 0,
    None: 0,
}
_ACADEMIC_SNIPPET_WORD_LIMIT = 40
_ACADEMIC_SHORTCUT_GENERIC_TERMS = frozenset(
    {
        "academic",
        "benchmark",
        "benchmarks",
        "evaluation",
        "generation",
        "grounded",
        "large",
        "language",
        "model",
        "models",
        "paper",
        "papers",
        "preprint",
        "recent",
        "research",
        "retrieval",
        "review",
        "study",
        "studies",
        "survey",
        "system",
        "systems",
    }
)


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


def _shortcut_focus_terms(text: str) -> set[str]:
    normalized = normalize_query_text(text)
    return {
        token
        for token in query_tokens(normalized)
        if (
            (token.isascii() and len(token) >= 4 and token not in _ACADEMIC_SHORTCUT_GENERIC_TERMS)
            or (not token.isascii())
        )
    }


def _trim_query_aligned_snippet(query: str, snippet: str) -> str:
    words = snippet.split()
    if len(words) <= _ACADEMIC_SNIPPET_WORD_LIMIT:
        return snippet

    query_terms = _shortcut_focus_terms(query)
    if not query_terms:
        return " ".join(words[:_ACADEMIC_SNIPPET_WORD_LIMIT]).strip()

    best_start = 0
    best_score = -1
    max_start = max(0, len(words) - _ACADEMIC_SNIPPET_WORD_LIMIT)
    for start in range(max_start + 1):
        window_words = words[start : start + _ACADEMIC_SNIPPET_WORD_LIMIT]
        window_text = " ".join(window_words)
        score = len(query_terms & _shortcut_focus_terms(window_text))
        if score > best_score:
            best_score = score
            best_start = start

    trimmed_words = words[best_start : best_start + _ACADEMIC_SNIPPET_WORD_LIMIT]
    trimmed = " ".join(trimmed_words).strip()
    if best_start > 0:
        trimmed = f"...{trimmed}"
    if best_start + _ACADEMIC_SNIPPET_WORD_LIMIT < len(words):
        trimmed = f"{trimmed}..."
    return trimmed


def academic_fixture_shortcut_allowed(
    *,
    query: str,
    title: str,
    snippet: str,
    url: str,
    year: int | None = None,
) -> bool:
    normalized = _normalize_record(
        {
            "title": title,
            "url": url,
            "snippet": snippet,
            "year": year,
        }
    )
    if normalized is None:
        return False

    alignment_score = academic_alignment_score(query, normalized)
    if alignment_score < _MIN_ACADEMIC_LIVE_SCORE:
        return False

    query_terms = _shortcut_focus_terms(query)
    if not query_terms:
        return alignment_score >= (_MIN_ACADEMIC_LIVE_SCORE + 2)

    record_terms = _shortcut_focus_terms(f"{title} {snippet}")
    required_overlap = 1 if len(query_terms) == 1 else 2
    return len(query_terms & record_terms) >= required_overlap


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
                "snippet": _trim_query_aligned_snippet(query, normalized["snippet"]),
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
