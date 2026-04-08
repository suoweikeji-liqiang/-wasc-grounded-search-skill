"""Deterministic query normalization utilities."""

from __future__ import annotations

import re
from unicodedata import normalize

_PUNCT_TRANSLATIONS = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "；": ";",
        "：": ":",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "／": "/",
        "—": "-",
        "－": "-",
        "、": " ",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)


def normalize_query_text(query: str) -> str:
    """Normalize user query for deterministic classification."""

    normalized = normalize("NFKC", query)
    normalized = normalized.translate(_PUNCT_TRANSLATIONS)
    normalized = normalized.strip().lower()
    return _WHITESPACE_RE.sub(" ", normalized)


def query_tokens(normalized_query: str) -> tuple[str, ...]:
    """Return deterministic token sequence from normalized query text."""

    return tuple(_TOKEN_RE.findall(normalized_query))
