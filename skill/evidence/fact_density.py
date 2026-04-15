"""Fact-density scoring for paragraph-level evidence extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ISO_DATE_RE = re.compile(
    r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"
)
_US_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s*(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_CHINESE_DATE_RE = re.compile(
    r"(?:19|20)\d{2}\s*\u5e74\s*\d{1,2}\s*\u6708\s*\d{1,2}\s*\u65e5"
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

_VERSION_RE = re.compile(
    r"(?:"
    r"\bversion\s+[a-z0-9][\w.\-]*"
    r"|\bv\d+(?:\.\d+)*\b"
    r"|\brev(?:ision)?\s+[a-z0-9][\w.\-]*"
    r"|\bed(?:ition)?\s+[a-z0-9][\w.\-]*"
    r"|\brevised\b"
    r"|\bfinal rule\b"
    r"|\binterim final rule\b"
    r"|\bnotice\b"
    r"|\u7248\u672c"
    r"|\u4fee\u8ba2"
    r"|\u53d1\u5e03"
    r"|\u751f\u6548"
    r")",
    re.IGNORECASE,
)

_CLAUSE_RE = re.compile(
    r"(?:"
    r"\barticle\s+\d+[a-z0-9.\-]*"
    r"|\bsection\s+\d+[a-z0-9.\-]*"
    r"|\bclause\s+\d+[a-z0-9.\-]*"
    r"|\bparagraph\s+\d+[a-z0-9.\-]*"
    r"|\bpart\s+\d+[a-z0-9.\-]*"
    r"|\bitem\s+\d+[a-z0-9.\-]*"
    r"|\u7b2c[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343]+(?:\u6761|\u7ae0|\u8282)"
    r")",
    re.IGNORECASE,
)

_NUMERIC_THRESHOLD_RE = re.compile(
    r"(?:"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*(?:%|percent|bps|usd|eur|rmb|cny|gbp|jpy)"
    r"|(?:\$|EUR|USD|GBP|CNY)\s?\d+(?:\.\d+)?"
    r"|\bQ[1-4]\s*(?:19|20)?\d{2}\b"
    r"|\bFY\s*(?:19|20)?\d{2}\b"
    r")",
    re.IGNORECASE,
)

_AUTHORITY_TOKENS = (
    "state council",
    "ministry",
    "commission",
    "authority",
    "administration",
    "bureau",
    "department",
    "regulator",
    "agency",
    "federal",
    "european",
    "parliament",
    "congress",
    "directive",
    "regulation",
    "rule",
    "\u56fd\u52a1\u9662",
    "\u90e8",
    "\u59d4\u5458\u4f1a",
    "\u5c40",
    "\u901a\u77e5",
    "\u516c\u544a",
    "\u51b3\u5b9a",
    "\u89c4\u5b9a",
    "\u529e\u6cd5",
)

_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?;:\u3002\uff01\uff1f\uff1b])\s+")


@dataclass(frozen=True)
class ScoredParagraph:
    text: str
    score: float


def _clean(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _split_long_block(block: str, *, min_chars: int, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    parts = [part.strip() for part in _SENTENCE_BOUNDARY_RE.split(block) if part.strip()]
    if len(parts) <= 1:
        return [block[i : i + max_chars].strip() for i in range(0, len(block), max_chars)]

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip() if current else part
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = part
            continue
        current = candidate
    if current:
        chunks.append(current)

    normalized: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            normalized.append(chunk)
            continue
        normalized.extend(
            segment.strip()
            for segment in (
                chunk[i : i + max_chars] for i in range(0, len(chunk), max_chars)
            )
            if segment.strip()
        )
    return [chunk for chunk in normalized if len(chunk) >= min_chars]


def split_paragraphs(
    text: str,
    *,
    min_chars: int = 40,
    max_chars: int = 480,
) -> list[str]:
    """Split page text into paragraph-sized chunks."""

    if not text:
        return []

    raw_blocks = re.split(r"\r?\n\s*\r?\n+", text)
    if len(raw_blocks) == 1:
        raw_blocks = text.splitlines()

    blocks = [_clean(block) for block in raw_blocks]
    blocks = [block for block in blocks if block]

    merged: list[str] = []
    buffer = ""
    for block in blocks:
        candidate = f"{buffer} {block}".strip() if buffer else block
        if len(candidate) < min_chars:
            buffer = candidate
            continue
        if buffer:
            block = candidate
            buffer = ""
        merged.extend(_split_long_block(block, min_chars=min_chars, max_chars=max_chars))

    if buffer:
        merged.extend(_split_long_block(buffer, min_chars=min_chars, max_chars=max_chars))

    deduped: list[str] = []
    seen: set[str] = set()
    for block in merged:
        cleaned = _clean(block)
        if len(cleaned) < min_chars or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _authority_hits(text_lower: str) -> int:
    return sum(1 for token in _AUTHORITY_TOKENS if token in text_lower)


def fact_density_score(paragraph: str) -> float:
    """Score a paragraph by the density of fact-bearing tokens."""

    if not paragraph:
        return 0.0

    text_lower = paragraph.lower()
    date_hits = (
        len(_ISO_DATE_RE.findall(paragraph))
        + len(_US_DATE_RE.findall(paragraph))
        + len(_CHINESE_DATE_RE.findall(paragraph))
    )
    year_hits = len(_YEAR_RE.findall(paragraph))
    version_hits = len(_VERSION_RE.findall(paragraph))
    clause_hits = len(_CLAUSE_RE.findall(paragraph))
    numeric_hits = len(_NUMERIC_THRESHOLD_RE.findall(paragraph))
    authority_hits = _authority_hits(text_lower)

    weighted = (
        3.2 * date_hits
        + 0.4 * max(0, year_hits - date_hits)
        + 2.0 * version_hits
        + 2.6 * clause_hits
        + 1.2 * numeric_hits
        + 0.8 * authority_hits
    )
    length_factor = min(1.0, len(paragraph) / 220.0)
    return weighted * (0.55 + 0.45 * length_factor)


def query_overlap_score(paragraph: str, query_terms: tuple[str, ...]) -> int:
    if not paragraph or not query_terms:
        return 0
    text_lower = paragraph.lower()
    return sum(1 for term in query_terms if term in text_lower)


def rank_fact_paragraphs(
    text: str,
    *,
    query_terms: tuple[str, ...] = (),
    limit: int = 4,
    min_chars: int = 40,
    max_chars: int = 480,
    min_score: float = 0.0,
) -> list[ScoredParagraph]:
    """Return top paragraphs ranked by fact density and query overlap."""

    paragraphs = split_paragraphs(text, min_chars=min_chars, max_chars=max_chars)
    if not paragraphs:
        return []

    normalized_terms = tuple(term.lower() for term in query_terms if term)
    scored: list[tuple[float, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        density = fact_density_score(paragraph)
        overlap = query_overlap_score(paragraph, normalized_terms)
        total = density + 1.5 * overlap
        if total < min_score:
            continue
        scored.append((total, -index, paragraph))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [ScoredParagraph(text=paragraph, score=score) for score, _, paragraph in scored[:limit]]
