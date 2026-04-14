"""Helpers for shaping industry snippets from live fetches."""

from __future__ import annotations

import re

from skill.orchestrator.normalize import normalize_query_text, query_tokens

_SEGMENT_SPLIT_RE = re.compile(r"(?<=[\.\!\?。！？；;])\s+|\n+")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _query_terms(query: str) -> tuple[str, ...]:
    normalized = normalize_query_text(query)
    tokens = []
    for token in query_tokens(normalized):
        if token.isdigit() and len(token) == 4:
            tokens.append(token)
            continue
        if token.isascii():
            if len(token) >= 4:
                tokens.append(token)
            continue
        tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def _overlap_score(query: str, text: str) -> int:
    terms = _query_terms(query)
    if not terms:
        return 0
    normalized_text = normalize_query_text(text)
    text_tokens = set(query_tokens(normalized_text))
    return sum(1 for term in terms if term in text_tokens)


def _page_segments(page_text: str) -> list[str]:
    cleaned = _clean_text(page_text)
    if not cleaned:
        return []
    segments = [_clean_text(part) for part in _SEGMENT_SPLIT_RE.split(cleaned) if _clean_text(part)]
    if segments:
        return segments
    return [cleaned]


def _windowed_excerpt(text: str, *, max_chars: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def _best_word_window(
    *,
    query: str,
    text: str,
    max_chars: int,
) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned

    words = cleaned.split()
    if len(words) <= 1:
        return cleaned[:max_chars].rstrip()

    best_window = cleaned[:max_chars]
    best_candidate = (-1, 0, -max_chars)
    for start in range(0, len(words), 12):
        window_words: list[str] = []
        char_count = 0
        for word in words[start:]:
            projected = char_count + len(word) + (1 if window_words else 0)
            if window_words and projected > max_chars:
                break
            window_words.append(word)
            char_count = projected
        if not window_words:
            continue
        window = " ".join(window_words)
        candidate = (
            _overlap_score(query, window),
            len(window_words),
            -abs(len(window) - max_chars),
        )
        if candidate > best_candidate:
            best_candidate = candidate
            best_window = window
    return best_window.rstrip()


def _best_page_excerpt(
    *,
    query: str,
    page_text: str,
    max_chars: int,
) -> str:
    cleaned = _clean_text(page_text)
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    segments = _page_segments(page_text)
    best_segment = max(
        segments,
        key=lambda segment: (_overlap_score(query, segment), -abs(len(segment) - max_chars)),
        default="",
    )
    if _overlap_score(query, best_segment) > 0:
        return _best_word_window(query=query, text=best_segment, max_chars=max_chars)

    return _best_word_window(query=query, text=cleaned, max_chars=max_chars)


def build_industry_snippet(
    *,
    query: str,
    candidate_snippet: str,
    page_text: str,
    max_chars: int = 320,
) -> str:
    candidate = _windowed_excerpt(candidate_snippet, max_chars=max_chars)
    page_excerpt = _best_page_excerpt(
        query=query,
        page_text=page_text,
        max_chars=max_chars,
    )
    if not candidate and not page_excerpt:
        return ""

    candidate_score = _overlap_score(query, candidate)
    page_score = _overlap_score(query, page_excerpt)

    if candidate_score >= page_score and candidate:
        return candidate
    if page_excerpt:
        return page_excerpt
    return candidate
