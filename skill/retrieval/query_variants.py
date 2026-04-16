"""Bounded route-aware query variant generation for retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from skill.orchestrator.intent import classify_query
from skill.orchestrator.normalize import normalize_query_text
from skill.orchestrator.query_traits import QueryTraits, derive_query_traits

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]

MAX_QUERY_VARIANTS = 3
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_YEAR_RE = re.compile(r"(?<!\d)20\d{2}(?!\d)")
_INDUSTRY_SHARE_MARKERS: tuple[str, ...] = (
    "\u4efd\u989d",
    "\u5e02\u5360\u7387",
    "\u5e02\u573a\u4efd\u989d",
    "share",
    "market share",
)
_INDUSTRY_FORECAST_MARKERS: tuple[str, ...] = (
    "\u8d8b\u52bf",
    "\u9884\u6d4b",
    "trend",
    "forecast",
    "outlook",
)
_INDUSTRY_CJK_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("\u5148\u8fdb\u5c01\u88c5", "advanced packaging"),
    ("\u52a8\u529b\u7535\u6c60", "ev battery"),
    ("\u65b0\u80fd\u6e90\u6c7d\u8f66", "ev"),
    ("\u5e02\u573a\u4efd\u989d", "market share"),
    ("\u5e02\u5360\u7387", "market share"),
    ("\u5e02\u573a\u89c4\u6a21", "market size"),
    ("\u51fa\u8d27\u91cf", "shipments"),
    ("\u534a\u5bfc\u4f53", "semiconductor"),
    ("\u667a\u80fd\u624b\u673a", "smartphone"),
    ("\u4ea7\u80fd", "capacity"),
    ("\u56de\u6536", "recycling"),
    ("\u7535\u6c60", "battery"),
    ("\u5c01\u88c5", "packaging"),
    ("\u82af\u7247", "chip"),
    ("\u5e02\u573a", "market"),
    ("\u4efd\u989d", "share"),
    ("\u9884\u6d4b", "forecast"),
    ("\u8d8b\u52bf", "trend"),
    ("\u5c55\u671b", "outlook"),
)
_ACADEMIC_REMOVABLE_MARKERS: tuple[str, ...] = (
    "paper",
    "papers",
    "research",
    "study",
    "studies",
)
_ACADEMIC_ASCII_CORE_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
    }
)
_ACADEMIC_ASCII_NOISE_RE = re.compile(r"[^a-z0-9\s-]")
_ACADEMIC_SOURCE_HINTS: tuple[str, ...] = (
    "arxiv",
    "europe pmc",
    "semantic scholar",
    "openalex",
)
_ACADEMIC_EVIDENCE_TYPE_TERMS: tuple[str, ...] = (
    "annotation",
    "annotations",
    "attribution",
    "benchmark",
    "benchmarks",
    "citation",
    "citations",
    "comparison",
    "comparisons",
    "dataset",
    "datasets",
    "evaluation",
    "evaluations",
    "experiment",
    "experiments",
    "factuality",
    "grounding",
    "review",
    "reviews",
    "survey",
    "surveys",
)
_ACADEMIC_THREE_WORD_PHRASE_TAILS: frozenset[str] = frozenset(
    {"annotation", "model", "models", "rate"}
)
_QUERY_WORD_RE = re.compile(r"[a-z0-9-]+|[\u4e00-\u9fff]", re.IGNORECASE)
_CROSS_DOMAIN_SPLIT_MARKERS: tuple[str, ...] = (
    " impact on ",
    " effect on ",
    " impact of ",
    " effect of ",
    " and ",
    " 与 ",
    " 对 ",
    " 对于 ",
)
_LOW_INFORMATION_QUERY_TERMS: frozenset[str] = frozenset(
    {
        "official",
        "officially",
        "text",
        "guidance",
        "definition",
        "definitions",
        "exact",
        "current",
        "latest",
        "final",
        "notice",
    }
)
_DOCUMENT_MARKERS: tuple[str, ...] = (
    "form 10-k",
    "form 10-q",
    "form 8-k",
    "form 20-f",
    "form 6-k",
    "annual report",
    "quarterly report",
    "earnings materials",
    "earnings release",
    "earnings presentation",
    "filing",
)
_DOCUMENT_MARKER_PATTERN = re.compile(
    "|".join(
        rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])"
        for marker in sorted(_DOCUMENT_MARKERS, key=len, reverse=True)
    )
)
_DOCUMENT_NOISE_TERMS: frozenset[str] = frozenset(
    {
        *tuple(_LOW_INFORMATION_QUERY_TERMS),
        "document",
        "filing",
        "report",
        "reports",
        "materials",
        "release",
        "presentation",
        "year",
        "fiscal",
    }
)
_FISCAL_YEAR_RE = re.compile(r"^(?:fy)?20\d{2}$")


@dataclass(frozen=True)
class QueryVariant:
    query: str
    reason_code: str


def _uses_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _append_terms(query: str, *terms: str) -> str:
    normalized_query = normalize_query_text(query)
    missing_terms = [
        term
        for term in terms
        if term and normalize_query_text(term) not in normalized_query
    ]
    if not missing_terms:
        return query.strip()
    return f"{query.strip()} {' '.join(missing_terms)}".strip()


def _contains_any_marker(normalized_query: str, markers: tuple[str, ...]) -> bool:
    return any(normalize_query_text(marker) in normalized_query for marker in markers)


def _remove_ascii_marker(text: str, marker: str) -> str:
    return re.sub(
        rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
        " ",
        text,
    )


def _compact_query_text(text: str) -> str:
    compact = normalize_query_text(text)
    compact = re.sub(r"\s+", " ", compact).strip(" -")
    return compact


def _split_query_words(text: str) -> list[str]:
    normalized = normalize_query_text(text)
    return [word for word in normalized.split(" ") if word]


def _content_words(text: str) -> list[str]:
    normalized = normalize_query_text(text)
    return [word for word in _QUERY_WORD_RE.findall(normalized) if word]


def _prune_query_terms(
    text: str,
    *,
    removable_terms: frozenset[str],
) -> str:
    words = _content_words(text)
    kept_words = [
        word
        for word in words
        if word not in removable_terms
        and not _YEAR_RE.fullmatch(word)
        and not _FISCAL_YEAR_RE.fullmatch(word)
    ]
    return _compact_query_text(" ".join(kept_words))


def _build_core_focus_query(query: str) -> str | None:
    compacted = _prune_query_terms(
        query,
        removable_terms=_LOW_INFORMATION_QUERY_TERMS,
    )
    normalized_original = normalize_query_text(query)
    if not compacted or compacted == normalized_original:
        return None
    compacted_words = _split_query_words(compacted)
    original_ascii_words = [
        word
        for word in _content_words(query)
        if word.isascii() and any(char.isalnum() for char in word)
    ]
    if (
        _uses_cjk(query)
        and not original_ascii_words
        and compacted_words
        and all(len(word) == 1 and _uses_cjk(word) for word in compacted_words)
    ):
        return None
    return compacted


def _build_academic_ascii_core_query(query: str) -> str | None:
    normalized = normalize_query_text(query)
    ascii_words = [
        word
        for word in _content_words(query)
        if (
            word.isascii()
            and any(char.isalnum() for char in word)
            and not _YEAR_RE.fullmatch(word)
            and word not in _ACADEMIC_ASCII_CORE_STOPWORDS
        )
    ]
    deduped_words = list(dict.fromkeys(ascii_words))
    if len(deduped_words) < 3:
        return None

    compacted = _compact_query_text(" ".join(deduped_words))
    if not compacted:
        return None
    if compacted == normalized:
        return None
    if not (
        _uses_cjk(query)
        or _ACADEMIC_ASCII_NOISE_RE.search(normalized) is not None
    ):
        return None
    return compacted


def _split_cross_domain_fragments(query: str) -> tuple[str, ...]:
    normalized = normalize_query_text(query)
    for marker in _CROSS_DOMAIN_SPLIT_MARKERS:
        if marker not in normalized:
            continue
        left, right = normalized.split(marker, 1)
        left = _compact_query_text(left)
        right = _compact_query_text(right)
        fragments = tuple(
            fragment
            for fragment in (left, right)
            if len(_split_query_words(fragment)) >= 3
        )
        if len(fragments) >= 2:
            return fragments
    return ()


def _best_cross_domain_fragment(
    *,
    query: str,
    primary_route: ConcreteRoute,
    target_route: ConcreteRoute,
) -> str | None:
    fragments = _split_cross_domain_fragments(query)
    if not fragments:
        return None

    scored_fragments: list[tuple[int, int, int, str]] = []
    for index, fragment in enumerate(fragments):
        classified = classify_query(fragment)
        route_score = int(classified.scores[target_route])
        position_score = 0
        if target_route == primary_route and index == 0:
            position_score = 1
        elif target_route != primary_route and index == len(fragments) - 1:
            position_score = 1
        scored_fragments.append(
            (
                route_score,
                position_score,
                len(_split_query_words(fragment)),
                fragment,
            )
        )

    scored_fragments.sort(reverse=True)
    best_fragment = scored_fragments[0][3]
    return None if best_fragment == normalize_query_text(query) else best_fragment


def _document_focus_parts(query: str) -> tuple[str, str, str] | None:
    normalized = normalize_query_text(query)
    match = _DOCUMENT_MARKER_PATTERN.search(normalized)
    if match is None:
        return None

    marker = match.group(0)
    prefix = normalized[: match.start()]
    suffix = normalized[match.end() :]
    entity = _prune_query_terms(prefix, removable_terms=_DOCUMENT_NOISE_TERMS)
    concept = _prune_query_terms(suffix, removable_terms=_DOCUMENT_NOISE_TERMS)
    if not entity or not concept:
        return None
    return entity, marker, concept


def _build_document_focus_query(query: str) -> str | None:
    parts = _document_focus_parts(query)
    if parts is None:
        return None
    entity, marker, concept = parts
    focused = _compact_query_text(f"{entity} {marker} {concept}")
    return None if focused == normalize_query_text(query) else focused


def _build_document_concept_focus_query(query: str) -> str | None:
    parts = _document_focus_parts(query)
    if parts is None:
        return None
    entity, _, concept = parts
    focused = _compact_query_text(f"{entity} {concept}")
    return None if focused == normalize_query_text(query) else focused


def _academic_source_hint(normalized_query: str) -> str | None:
    for marker in _ACADEMIC_SOURCE_HINTS:
        if normalize_query_text(marker) in normalized_query:
            return marker
    return None


def _condense_academic_query(
    query: str,
    *,
    keep_source_hint: bool,
) -> str:
    condensed = normalize_query_text(query)
    condensed = _YEAR_RE.sub(" ", condensed)
    for marker in _ACADEMIC_REMOVABLE_MARKERS:
        condensed = _remove_ascii_marker(condensed, marker)
    if not keep_source_hint:
        for marker in _ACADEMIC_SOURCE_HINTS:
            condensed = _remove_ascii_marker(condensed, marker)
    return _compact_query_text(condensed)


def _build_academic_phrase_locked_query(query: str) -> str | None:
    words = _split_query_words(
        _condense_academic_query(
            query,
            keep_source_hint=False,
        )
    )
    candidates: list[tuple[int, int, str]] = []
    seen_phrases: set[str] = set()
    for index, word in enumerate(words[:-1]):
        if "-" not in word:
            continue
        next_word = words[index + 1]
        if not next_word or _YEAR_RE.fullmatch(next_word):
            continue

        phrase_words = [word, next_word]
        if index + 2 < len(words) and words[index + 2] in _ACADEMIC_THREE_WORD_PHRASE_TAILS:
            phrase_words.append(words[index + 2])
        phrase = " ".join(phrase_words)
        if phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)
        candidates.append((word.count("-"), index, phrase))

    if len(candidates) < 2:
        return None

    selected_phrases = [
        phrase
        for _, _, phrase in sorted(candidates, key=lambda item: (-item[0], item[1]))[:2]
    ]
    locked_query = _condense_academic_query(
        query,
        keep_source_hint=False,
    )
    for phrase in selected_phrases:
        locked_query = locked_query.replace(phrase, f'"{phrase}"', 1)
    return _compact_query_text(locked_query)


def _build_industry_cjk_gloss_query(query: str) -> str | None:
    if not _uses_cjk(query):
        return None

    normalized = normalize_query_text(query)
    expanded = normalized
    for source_text, english_text in _INDUSTRY_CJK_GLOSSARY:
        expanded = expanded.replace(source_text, f" {english_text} ")

    ascii_words = [
        word
        for word in _split_query_words(_compact_query_text(expanded))
        if word.isascii() and any(char.isalnum() for char in word)
    ]
    deduped_words = list(dict.fromkeys(ascii_words))
    if len(deduped_words) < 3:
        return None

    gloss_query = _compact_query_text(" ".join(deduped_words))
    if not gloss_query or gloss_query == normalized:
        return None
    return gloss_query


def _build_academic_evidence_type_focus_query(query: str) -> str | None:
    condensed = _condense_academic_query(
        query,
        keep_source_hint=False,
    )
    words = _split_query_words(condensed)
    evidence_terms: list[str] = []
    for word in words:
        if word in _ACADEMIC_EVIDENCE_TYPE_TERMS and word not in evidence_terms:
            evidence_terms.append(word)
    if len(evidence_terms) < 2:
        return None

    focus_parts: list[str] = []
    phrase_locked_query = _build_academic_phrase_locked_query(query)
    if phrase_locked_query is not None:
        phrase_words = [
            word
            for word in _split_query_words(phrase_locked_query.replace('"', " "))
            if word not in _ACADEMIC_EVIDENCE_TYPE_TERMS
        ]
        if phrase_words:
            focus_parts.append(" ".join(phrase_words[:2]))
    if not focus_parts:
        core_terms = [
            word
            for word in words
            if word not in _ACADEMIC_EVIDENCE_TYPE_TERMS
        ]
        if core_terms:
            focus_parts.append(" ".join(core_terms[:2]))

    focus_parts.extend(evidence_terms[:4])
    evidence_focus_query = _compact_query_text(" ".join(focus_parts))
    if not evidence_focus_query or evidence_focus_query == condensed:
        return None
    return evidence_focus_query


def _policy_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    if route_label == "mixed":
        focus_terms = ("\u653f\u7b56", "\u76d1\u7ba1") if use_cjk else ("policy", "regulation")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="policy_focus",
            )
        )

    if traits.is_policy_change or traits.has_version_intent:
        revision_terms = ("\u4fee\u8ba2", "\u53d8\u5316") if use_cjk else ("revision", "amendment")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *revision_terms),
                reason_code="policy_change",
            )
        )

    if traits.has_effective_date_intent or traits.has_year:
        effective_terms = ("\u751f\u6548", "\u65f6\u95f4") if use_cjk else ("effective date",)
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *effective_terms),
                reason_code="policy_effective_date",
            )
        )

    return candidates


def _industry_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    normalized_query = normalize_query_text(query)
    has_share_language = _contains_any_marker(normalized_query, _INDUSTRY_SHARE_MARKERS)
    has_forecast_language = _contains_any_marker(normalized_query, _INDUSTRY_FORECAST_MARKERS)
    cjk_gloss_query = _build_industry_cjk_gloss_query(query)

    if cjk_gloss_query is not None:
        candidates.append(
            QueryVariant(
                query=cjk_gloss_query,
                reason_code="industry_cjk_gloss",
            )
        )

    if route_label == "mixed":
        focus_terms = ("\u4ea7\u4e1a", "\u5e02\u573a") if use_cjk else ("industry", "market")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="industry_focus",
            )
        )

    if (traits.has_trend_intent or traits.has_year) and not (
        has_share_language or has_forecast_language
    ):
        trend_terms = ("\u8d8b\u52bf", "\u9884\u6d4b") if use_cjk else ("trend", "forecast")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *trend_terms),
                reason_code="industry_trend",
            )
        )

    if traits.has_trend_intent and not has_share_language:
        share_terms = ("\u5e02\u573a", "\u4efd\u989d") if use_cjk else ("market", "share")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *share_terms),
                reason_code="industry_share",
            )
        )

    return candidates


def _academic_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    normalized_query = normalize_query_text(query)
    source_hint = _academic_source_hint(normalized_query)
    phrase_locked_query = _build_academic_phrase_locked_query(query)
    evidence_type_focus_query = _build_academic_evidence_type_focus_query(query)
    ascii_core_query = _build_academic_ascii_core_query(query)
    topic_focus_query = _condense_academic_query(
        query,
        keep_source_hint=False,
    )

    if ascii_core_query is not None:
        candidates.append(
            QueryVariant(
                query=ascii_core_query,
                reason_code="academic_ascii_core",
            )
        )

    if source_hint is not None:
        source_hint_query = _condense_academic_query(
            query,
            keep_source_hint=True,
        )
        if source_hint not in normalize_query_text(source_hint_query):
            source_hint_query = _append_terms(source_hint_query, source_hint)
        candidates.append(
            QueryVariant(
                query=source_hint_query,
                reason_code="academic_source_hint",
            )
        )

    if phrase_locked_query:
        candidates.append(
            QueryVariant(
                query=phrase_locked_query,
                reason_code="academic_phrase_locked",
            )
        )

    if topic_focus_query and topic_focus_query != normalized_query:
        candidates.append(
            QueryVariant(
                query=topic_focus_query,
                reason_code="academic_topic_focus",
            )
        )

    if route_label == "mixed":
        focus_terms = ("\u8bba\u6587", "\u7814\u7a76") if use_cjk else ("paper", "research")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="academic_focus",
            )
        )

    lookup_terms = ("\u8bba\u6587", "\u7814\u7a76") if use_cjk else ("paper", "research")
    lookup_base_query = topic_focus_query or query
    candidates.append(
        QueryVariant(
            query=_append_terms(lookup_base_query, *lookup_terms),
            reason_code="academic_lookup",
        )
    )

    if traits.has_year:
        benchmark_terms = ("\u7efc\u8ff0", "\u57fa\u51c6") if use_cjk else ("survey", "benchmark")
        candidates.append(
            QueryVariant(
                query=_append_terms(lookup_base_query, *benchmark_terms),
                reason_code="academic_benchmark",
            )
        )

    if evidence_type_focus_query:
        candidates.append(
            QueryVariant(
                query=evidence_type_focus_query,
                reason_code="academic_evidence_type_focus",
            )
        )

    return candidates


def build_query_variants(
    *,
    query: str,
    route_label: RouteLabel,
    primary_route: ConcreteRoute,
    supplemental_route: ConcreteRoute | None,
    target_route: ConcreteRoute,
    variant_limit: int = MAX_QUERY_VARIANTS,
) -> tuple[QueryVariant, ...]:
    limit = max(1, variant_limit)
    traits = derive_query_traits(query)
    use_cjk = _uses_cjk(query)
    candidates: list[QueryVariant] = [
        QueryVariant(query=query.strip(), reason_code="original")
    ]

    cross_domain_fragment = None
    if route_label == "mixed":
        cross_domain_fragment = _best_cross_domain_fragment(
            query=query,
            primary_route=primary_route,
            target_route=target_route,
        )
        if cross_domain_fragment is not None:
            candidates.append(
                QueryVariant(
                    query=cross_domain_fragment,
                    reason_code="cross_domain_fragment_focus",
                )
            )

    if target_route == "industry":
        document_focus_query = _build_document_focus_query(query)
        if document_focus_query is not None:
            candidates.append(
                QueryVariant(
                    query=document_focus_query,
                    reason_code="document_focus",
                )
            )
        document_concept_focus_query = _build_document_concept_focus_query(query)
        if document_concept_focus_query is not None:
            candidates.append(
                QueryVariant(
                    query=document_concept_focus_query,
                    reason_code="document_concept_focus",
                )
            )

    core_focus_query = _build_core_focus_query(query)
    if core_focus_query is not None and target_route != "academic":
        candidates.append(
            QueryVariant(
                query=core_focus_query,
                reason_code="core_focus",
            )
        )

    if target_route == "policy":
        candidates.extend(
            _policy_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )
    elif target_route == "industry":
        candidates.extend(
            _industry_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )
    else:
        candidates.extend(
            _academic_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )

    deduped: list[QueryVariant] = []
    seen_queries: set[str] = set()
    for candidate in candidates:
        normalized_query = normalize_query_text(candidate.query)
        if not normalized_query or normalized_query in seen_queries:
            continue
        deduped.append(candidate)
        seen_queries.add(normalized_query)
        if len(deduped) >= limit:
            break

    return tuple(deduped)
