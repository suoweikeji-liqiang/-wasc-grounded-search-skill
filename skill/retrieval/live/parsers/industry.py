"""Helpers for shaping industry snippets from live fetches."""

from __future__ import annotations


def build_industry_snippet(
    *,
    candidate_snippet: str,
    page_text: str,
    max_chars: int = 320,
) -> str:
    snippet = page_text.strip() or candidate_snippet.strip()
    if not snippet:
        return ""
    return snippet[:max_chars]
