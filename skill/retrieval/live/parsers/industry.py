"""Helpers for shaping industry snippets from live fetches."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from skill.evidence.fact_density import fact_density_score, rank_fact_paragraphs
from skill.orchestrator.normalize import normalize_query_text, query_tokens

_SEGMENT_SPLIT_RE = re.compile(r"(?<=[\.\!\?。！？；;])\s+|\n+")
_WHITESPACE_RE = re.compile(r"\s+")
_FOCUS_TERM_STOPWORDS = frozenset(
    {
        "official",
        "form",
        "filing",
        "report",
        "annual",
        "quarterly",
        "company",
        "document",
        "specification",
        "section",
        "sections",
        "discussion",
        "definition",
        "definitions",
        "policy",
        "basis",
        "changes",
        "change",
        "latest",
        "update",
        "version",
        "query",
    }
)
_SHORT_FOCUS_TOKENS = frozenset({"rfc", "cet1"})


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


def _focus_terms(text: str) -> tuple[str, ...]:
    normalized = normalize_query_text(text)
    tokens = []
    for token in query_tokens(normalized):
        if token in _FOCUS_TERM_STOPWORDS:
            continue
        if token.isdigit() and len(token) == 4:
            continue
        if token in _SHORT_FOCUS_TOKENS:
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


def _overlap_terms(terms: tuple[str, ...], text: str) -> int:
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


def _best_focus_word_window(
    *,
    text: str,
    focus_terms: tuple[str, ...],
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
    for start in range(0, len(words), 4):
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
            _overlap_terms(focus_terms, window),
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


def _excerpt_rank(
    *,
    query: str,
    text: str,
    max_chars: int,
) -> tuple[float, int, int]:
    cleaned = _clean_text(text)
    overlap = _overlap_score(query, cleaned)
    density = fact_density_score(cleaned)
    return (
        density + 2.0 * overlap,
        overlap,
        -abs(len(cleaned) - max_chars),
    )


def _best_fact_dense_page_excerpt(
    *,
    query: str,
    page_text: str,
    max_chars: int,
) -> str:
    ranked = rank_fact_paragraphs(
        page_text,
        query_terms=_query_terms(query),
        limit=3,
        min_chars=40,
        max_chars=max(max_chars, 360),
        min_score=1.0,
    )
    if not ranked:
        return ""

    best_excerpt = ""
    best_rank = (-1.0, -1, -max_chars)
    for item in ranked:
        excerpt = _best_word_window(query=query, text=item.text, max_chars=max_chars)
        rank = (
            fact_density_score(excerpt) + 2.0 * _overlap_score(query, excerpt),
            _overlap_score(query, excerpt),
            -abs(len(excerpt) - max_chars),
        )
        if rank > best_rank:
            best_rank = rank
            best_excerpt = excerpt
    return best_excerpt


def build_industry_snippet(
    *,
    query: str,
    candidate_snippet: str,
    page_text: str,
    max_chars: int = 320,
) -> str:
    candidate = _windowed_excerpt(candidate_snippet, max_chars=max_chars)
    page_candidates = [
        excerpt
        for excerpt in (
            _best_page_excerpt(
                query=query,
                page_text=page_text,
                max_chars=max_chars,
            ),
            _best_fact_dense_page_excerpt(
                query=query,
                page_text=page_text,
                max_chars=max_chars,
            ),
        )
        if excerpt
    ]
    page_excerpt = (
        max(
            page_candidates,
            key=lambda excerpt: _excerpt_rank(
                query=query,
                text=excerpt,
                max_chars=max_chars,
            ),
        )
        if page_candidates
        else ""
    )
    if not candidate and not page_excerpt:
        return ""
    if not candidate:
        return page_excerpt
    if not page_excerpt:
        return candidate

    candidate_rank = _excerpt_rank(query=query, text=candidate, max_chars=max_chars)
    page_rank = _excerpt_rank(query=query, text=page_excerpt, max_chars=max_chars)
    if candidate_rank >= page_rank:
        return candidate
    return page_excerpt


def extract_query_aligned_page_excerpt(
    *,
    html: str,
    query: str,
    title: str,
    candidate_snippet: str,
    max_chars: int = 320,
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    chunks: list[str] = []
    if soup.title:
        title_text = _clean_text(soup.title.get_text(" ", strip=True))
        if title_text:
            chunks.append(title_text)

    main = soup.find("main") or soup.body or soup
    for text in main.stripped_strings:
        cleaned = _clean_text(text)
        if cleaned:
            chunks.append(cleaned)

    if not chunks:
        return ""

    query_terms = _focus_terms(query)
    metadata_terms = set(_focus_terms(f"{title} {candidate_snippet}"))
    focus_terms = tuple(term for term in query_terms if term not in metadata_terms) or query_terms
    best_excerpt = ""
    best_candidate = (-1, -1, -1, -max_chars)

    for index, chunk in enumerate(chunks):
        focus_overlap = _overlap_terms(focus_terms, chunk)
        query_overlap = _overlap_terms(query_terms, chunk)
        if focus_overlap <= 0 and query_overlap <= 0:
            continue

        window_start = max(0, index - 8)
        window_end = min(len(chunks), index + 18)
        window_text = " ".join(chunks[window_start:window_end])
        compact_window = _best_focus_word_window(
            text=window_text,
            focus_terms=focus_terms,
            max_chars=max_chars,
        )
        candidate = (
            _overlap_terms(focus_terms, compact_window),
            _overlap_terms(query_terms, compact_window),
            focus_overlap,
            -abs(len(compact_window) - max_chars),
        )
        if candidate > best_candidate:
            best_candidate = candidate
            best_excerpt = compact_window

    if best_excerpt:
        return best_excerpt

    fallback_text = " ".join(chunks)
    return _best_page_excerpt(query=query, page_text=fallback_text, max_chars=max_chars)
