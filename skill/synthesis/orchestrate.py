"""End-to-end grounded answer orchestration."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import Mapping
from dataclasses import replace

from skill.api.schema import AnswerResponse, RetrieveCanonicalEvidenceItem, RetrieveResponse
from skill.config.retrieval import (
    COVERAGE_FRONTIER_MIN_REMAINING_SECONDS_TO_PROBE,
    COVERAGE_FRONTIER_PER_PROBE_TIMEOUT_SECONDS,
)
from skill.evidence.dedupe import collapse_evidence_records
from skill.evidence.models import CanonicalEvidence, EvidenceSlice, LinkedVariant, RawEvidenceRecord
from skill.evidence.normalize import normalize_hit_candidates
from skill.evidence.pack import build_evidence_pack
from skill.evidence.score import score_evidence_records
from skill.orchestrator.budget import (
    AnswerExecutionResult,
    RuntimeBudget,
    RuntimeTrace,
)
from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.retrieval.models import RetrievalFailureReason, RetrievalHit
from skill.retrieval.orchestrate import (
    Adapter,
    DEFAULT_EVIDENCE_TOP_K,
    DEFAULT_SUPPLEMENTAL_MIN_ITEMS,
    _shape_canonical_evidence,
    consume_last_retrieval_trace,
    execute_retrieval_pipeline,
)
from skill.retrieval.priority import prioritize_hits, score_query_alignment
from skill.retrieval.query_variants import _build_industry_cjk_gloss_query, build_query_variants
from skill.orchestrator.query_traits import derive_query_traits
from skill.synthesis.cache import ANSWER_CACHE, CachedAnswerEntry
from skill.synthesis.citation_check import validate_answer_citations
from skill.synthesis.generator import (
    ModelBackendError,
    ModelClient,
    generate_answer_draft,
)
from skill.synthesis.models import ClaimCitation, KeyPoint, SourceReference, StructuredAnswerDraft
from skill.synthesis.retrieval_policy import (
    CoverageFrontierProbe,
    attach_probe_alignment,
    build_coverage_frontier_candidates,
    decide_coverage_frontier_sufficiency,
    has_budget_for_coverage_frontier_probe,
    select_coverage_frontier_winner,
)
from skill.synthesis.prompt import build_grounded_answer_prompt
from skill.synthesis.state import determine_answer_status
from skill.synthesis.uncertainty import build_uncertainty_notes


_RELEVANCE_STOPWORDS = frozenset(
    {
        "about",
        "academic",
        "against",
        "answer",
        "benchmark",
        "date",
        "effect",
        "effective",
        "forecast",
        "guidance",
        "impact",
        "industry",
        "information",
        "latest",
        "market",
        "paper",
        "policy",
        "requirements",
        "research",
        "share",
        "system",
        "systems",
        "update",
        "version",
        "what",
    }
)
_SHORT_CONTENT_TOKENS = frozenset({"rag", "llm", "gpu", "ai", "xr"})

_ACADEMIC_LOOKUP_MARKERS = frozenset(
    {
        "arxiv",
        "attribution",
        "citation",
        "dataset",
        "datasets",
        "evaluation",
        "factuality",
        "grounding",
        "hallucination",
        "paper",
        "papers",
        "study",
        "preprint",
        "review",
        "survey",
        "benchmark",
        "benchmarks",
        "\u8bba\u6587",
        "\u7814\u7a76",
        "\u7efc\u8ff0",
    }
)
_ACADEMIC_LOOKUP_PHRASES = frozenset(
    {
        "europe pmc",
        "semantic scholar",
    }
)
_ACADEMIC_EXPLANATORY_MARKERS = frozenset(
    {"what", "how", "why", "compare", "comparison", "impact", "effect", "summary", "summarize"}
)
_INDUSTRY_LOOKUP_MARKERS = frozenset(
    {
        "forecast",
        "outlook",
        "market",
        "share",
        "capacity",
        "packaging",
        "recycling",
        "pricing",
        "\u8d8b\u52bf",
        "\u9884\u6d4b",
        "\u51fa\u8d27",
        "\u4efd\u989d",
        "\u5e02\u573a",
        "filing",
        "form",
        "annual",
        "report",
        "earnings",
        "guidance",
        "revenue",
        "segment",
        "backlog",
        "liquidity",
        "warranty",
        "reserves",
        "cet1",
        "rfc",
        "spec",
        "specification",
        "webauthn",
        "passkey",
        "discoverable",
        "credential",
        "chips",
        "cookie",
        "abnf",
        "signature",
        "input",
    }
)
_INDUSTRY_LOOKUP_PHRASES = frozenset(
    {
        "10-k",
        "10-q",
        "8-k",
        "20-f",
        "6-k",
        "annual report",
        "quarterly report",
        "set-cookie",
        "http message signatures",
    }
)
_INDUSTRY_EXPLANATORY_MARKERS = frozenset(
    {"what", "how", "why", "impact", "effect", "summary", "summarize"}
)
_POLICY_LOOKUP_MARKERS = frozenset(
    {
        "latest",
        "version",
        "effective",
        "date",
        "deadline",
        "deadlines",
        "timeline",
        "update",
        "registry",
        "guidance",
        "order",
        "notice",
        "official",
        "officiel",
        "directive",
        "regulation",
        "reglement",
        "article",
        "obligation",
        "obligations",
        "compliance",
        "milestone",
        "milestones",
        "eligibility",
        "scope",
        "transposition",
        "application",
        "commencement",
        "fips",
        "nist",
        "fda",
        "fcc",
        "epa",
        "ftc",
        "ofcom",
        "cisa",
        "circia",
        "pccp",
        "cgmp",
        "oai",
        "vai",
        "nai",
        "\u6700\u65b0",
        "\u7248\u672c",
        "\u751f\u6548",
        "\u65bd\u884c",
        "\u5b9e\u65bd",
        "\u901a\u77e5",
        "\u4fee\u8ba2",
        "\u53d8\u5316",
        "\u8c41\u514d",
        "\u573a\u666f",
        "\u6761\u6b3e",
    }
)
_POLICY_EXPLANATORY_MARKERS = frozenset(
    {"what", "how", "why", "impact", "effect", "summary", "summarize"}
)
_CROSS_DOMAIN_EFFECT_MARKERS = frozenset(
    {
        "impact on",
        "effect on",
        "impact of",
        "effect of",
        "\u5f71\u54cd",
        "\u6548\u5e94",
        "\u843d\u5730",
    }
)
_POLICY_EXEMPTION_MARKERS = frozenset(
    {"exemption", "exemptions", "scenario", "scenarios", "\u8c41\u514d", "\u573a\u666f"}
)
_POLICY_CHANGE_MARKERS = frozenset(
    {
        "change",
        "changes",
        "revision",
        "amendment",
        "update",
        "\u4fee\u8ba2",
        "\u53d8\u5316",
        "\u6761\u6b3e",
    }
)
_ACADEMIC_RESEARCH_MARKERS = frozenset({"research", "\u7814\u7a76"})
_ACADEMIC_BENCHMARK_MARKERS = frozenset(
    {"benchmark", "benchmarks", "\u57fa\u51c6", "\u8bc4\u6d4b"}
)
_ACADEMIC_PAPER_MARKERS = frozenset({"paper", "papers", "\u8bba\u6587"})
_MIXED_IMPACT_QUERY_MARKERS = frozenset(
    {"impact", "effect", "\u5f71\u54cd", "\u6548\u5e94"}
)
_ACADEMIC_LIST_INTENT_MARKERS = frozenset(
    {
        "benchmarks",
        "literature",
        "list",
        "papers",
        "studies",
        "surveys",
        "\u54ea\u4e9b",
        "\u54ea\u51e0",
        "\u5217\u51fa",
        "\u6709\u54ea\u4e9b",
    }
)
_COVERAGE_FRONTIER_VARIANT_PRIORITY: dict[str, int] = {
    "cross_domain_fragment_focus": 0,
    "document_focus": 1,
    "document_concept_focus": 2,
    "industry_focus": 3,
    "industry_trend": 4,
    "industry_share": 5,
    "core_focus": 6,
}
_ACADEMIC_EVIDENCE_LEVEL_PRIORITY = {
    "peer_reviewed": 3,
    "survey_or_review": 2,
    "preprint": 1,
    "metadata_only": 0,
    None: 0,
}
_ACADEMIC_FAST_PATH_GENERIC_TERMS = frozenset(
    {
        "academic",
        "benchmark",
        "benchmarks",
        "evaluation",
        "generation",
        "grounded",
        "paper",
        "papers",
        "peer",
        "preprint",
        "research",
        "retrieval",
        "review",
        "reviewed",
        "study",
        "studies",
        "survey",
        "system",
        "systems",
    }
)
_INDUSTRY_CONTEXT_GENERIC_TERMS = frozenset(
    {
        "annual",
        "forecast",
        "form",
        "filing",
        "guidance",
        "industry",
        "liquidity",
        "market",
        "outlook",
        "report",
        "research",
        "revenue",
        "sales",
        "segment",
        "share",
        "shipment",
        "shipments",
        "trend",
        "trends",
        "update",
        "warranty",
        "reserves",
        "市场",
        "趋势",
        "预测",
        "份额",
        "出货",
        "行业",
    }
)
_DATE_LITERAL_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_YEAR_LITERAL_RE = re.compile(r"20\d{2}")
_VERSION_LITERAL_RE = re.compile(r"version [^.;,)]+", re.IGNORECASE)


def _estimate_tokens(text: str) -> int:
    return len(text.split())


def _estimate_evidence_tokens(canonical_evidence: tuple[CanonicalEvidence, ...]) -> int:
    total = 0
    for record in canonical_evidence:
        if record.retained_slices:
            total += sum(max(1, slice_.token_estimate) for slice_ in record.retained_slices)
            continue
        total += max(1, _estimate_tokens(record.canonical_title))
    return total


def _estimate_response_tokens(response: AnswerResponse) -> int:
    total = _estimate_tokens(response.conclusion)
    total += sum(_estimate_tokens(key_point.statement) for key_point in response.key_points)
    total += sum(
        _estimate_tokens(citation.quote_text)
        for key_point in response.key_points
        for citation in key_point.citations
    )
    total += sum(_estimate_tokens(note) for note in response.uncertainty_notes)
    return total


def _content_terms(text: str) -> set[str]:
    normalized = normalize_query_text(text)
    return {
        token
        for token in query_tokens(normalized)
        if (
            (
                token.isascii()
                and (
                    (len(token) >= 4 and token not in _RELEVANCE_STOPWORDS)
                    or token in _SHORT_CONTENT_TOKENS
                )
            )
            or (token.isdigit() and len(token) == 4)
            or not token.isascii()
        )
    }


def _academic_focus_terms(text: str) -> set[str]:
    return {
        token
        for token in _content_terms(text)
        if token not in _ACADEMIC_FAST_PATH_GENERIC_TERMS
    }


def _industry_context_terms(text: str) -> set[str]:
    return {
        token
        for token in _content_terms(text)
        if not (token.isdigit() and len(token) == 4)
        and token not in _INDUSTRY_CONTEXT_GENERIC_TERMS
    }


def _industry_thematic_overlap(query: str, record: CanonicalEvidence) -> int:
    query_terms = _industry_context_terms(query)
    gloss_query = _build_industry_cjk_gloss_query(query)
    if gloss_query:
        query_terms.update(_industry_context_terms(gloss_query))
    if not query_terms:
        return 0

    record_terms = _industry_context_terms(record.canonical_title)
    for slice_ in record.retained_slices:
        record_terms.update(_industry_context_terms(slice_.text))
    return len(query_terms & record_terms)


def _best_slice_overlap(
    query_terms: set[str],
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> tuple[int, CanonicalEvidence | None, EvidenceSlice | None]:
    best_overlap = 0
    best_record: CanonicalEvidence | None = None
    best_slice: EvidenceSlice | None = None
    best_candidate = (0, -1, -10_000, "", "")

    for record in canonical_evidence:
        evidence_level_priority = _ACADEMIC_EVIDENCE_LEVEL_PRIORITY.get(
            record.evidence_level,
            0,
        )
        for slice_ in record.retained_slices:
            overlap = len(query_terms & _content_terms(slice_.text))
            candidate = (
                overlap,
                evidence_level_priority,
                -slice_.token_estimate,
                record.evidence_id,
                slice_.source_record_id,
            )
            if candidate > best_candidate:
                best_candidate = candidate
                best_overlap = overlap
                best_record = record
                best_slice = slice_

    return best_overlap, best_record, best_slice


def _best_route_slice_overlap(
    query_terms: set[str],
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    domain: str,
    route_role: str,
) -> tuple[int, CanonicalEvidence | None, EvidenceSlice | None]:
    filtered_records = tuple(
        record
        for record in canonical_evidence
        if record.domain == domain and record.route_role == route_role
    )
    return _best_slice_overlap(query_terms, filtered_records)


def _top_route_matches(
    query: str,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    domain: str,
    route_role: str,
    limit: int = 2,
) -> tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...]:
    query_terms = _content_terms(query)
    ranked_matches: list[tuple[int, int, float, str, CanonicalEvidence, EvidenceSlice]] = []

    for record in canonical_evidence:
        if record.domain != domain or record.route_role != route_role or not record.retained_slices:
            continue

        best_slice = max(
            record.retained_slices,
            key=lambda slice_: (
                len(query_terms & _content_terms(slice_.text)),
                slice_.score,
                -slice_.token_estimate,
                slice_.source_record_id,
            ),
        )
        overlap = len(query_terms & _content_terms(best_slice.text))
        alignment_score = score_query_alignment(
            query,
            route=domain,  # type: ignore[arg-type]
            title=record.canonical_title,
            snippet=" ".join(slice_.text for slice_ in record.retained_slices),
            url=record.canonical_url,
            authority=record.authority,
            publication_date=record.publication_date,
            effective_date=record.effective_date,
            version=record.version,
            year=record.year,
        )
        if overlap <= 0 and alignment_score <= 0:
            continue

        ranked_matches.append(
            (
                overlap,
                alignment_score,
                float(getattr(record, "total_score", 0.0)),
                record.evidence_id,
                record,
                best_slice,
            )
        )

    ranked_matches.sort(
        key=lambda item: (-item[0], -item[1], -item[2], item[3])
    )
    return tuple(
        (record, best_slice, overlap)
        for overlap, _, _, _, record, best_slice in ranked_matches[:limit]
    )


def _academic_fast_path_match_allowed(
    query: str,
    *,
    record: CanonicalEvidence,
    matched_slice: EvidenceSlice,
    slice_overlap: int,
) -> bool:
    query_terms = _academic_focus_terms(query)
    required_overlap = min(2, len(query_terms))
    if required_overlap <= 0:
        return True
    if slice_overlap >= required_overlap:
        return True

    combined_terms = _academic_focus_terms(record.canonical_title)
    combined_terms.update(_academic_focus_terms(matched_slice.text))
    combined_overlap = len(query_terms & combined_terms)
    if combined_overlap < required_overlap:
        return False

    alignment_score = score_query_alignment(
        query,
        route="academic",
        title=record.canonical_title,
        snippet=" ".join(slice_.text for slice_ in record.retained_slices),
        url=record.canonical_url,
        year=record.year,
    )
    return alignment_score >= max(5, required_overlap * 3)


def _academic_fast_path_runtime_ok(retrieval_response: RetrieveResponse) -> bool:
    if retrieval_response.status == "success":
        return True
    if retrieval_response.status != "partial":
        return False
    if not retrieval_response.gaps:
        return bool(retrieval_response.canonical_evidence)
    return all(gap.startswith("academic_") for gap in retrieval_response.gaps)


def _contains_marker(
    normalized_query: str,
    tokens: set[str],
    markers: frozenset[str],
) -> bool:
    return any(
        (marker in tokens) if marker.isascii() else (marker in normalized_query)
        for marker in markers
    )


def _query_contains_marker(query: str, markers: frozenset[str]) -> bool:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    return _contains_marker(normalized, tokens, markers)


def _query_uses_cjk(query: str) -> bool:
    return any(not character.isascii() for character in query)


def _is_academic_lookup_query(query: str) -> bool:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    if _contains_marker(
        normalized, tokens, _ACADEMIC_EXPLANATORY_MARKERS
    ):
        return False

    if (
        _contains_marker(normalized, tokens, _ACADEMIC_LOOKUP_MARKERS)
        or any(marker in normalized for marker in _ACADEMIC_LOOKUP_PHRASES)
        or "openalex" in tokens
    ):
        return True

    traits = derive_query_traits(query)
    return traits.has_year and len(_academic_focus_terms(query)) >= 3


def _is_policy_lookup_query(query: str) -> bool:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    traits = derive_query_traits(query)
    return (
        _contains_marker(normalized, tokens, _POLICY_LOOKUP_MARKERS)
        or traits.has_version_intent
        or traits.has_effective_date_intent
        or traits.is_policy_change
    ) and not _contains_marker(
        normalized, tokens, _POLICY_EXPLANATORY_MARKERS
    )


def _is_industry_lookup_query(query: str) -> bool:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    traits = derive_query_traits(query)
    return (
        _contains_marker(normalized, tokens, _INDUSTRY_LOOKUP_MARKERS)
        or any(marker in normalized for marker in _INDUSTRY_LOOKUP_PHRASES)
        or traits.has_trend_intent
    ) and not _contains_marker(
        normalized, tokens, _INDUSTRY_EXPLANATORY_MARKERS
    )


def _is_cross_domain_effect_query(query: str) -> bool:
    normalized = normalize_query_text(query)
    return any(marker in normalized for marker in _CROSS_DOMAIN_EFFECT_MARKERS) or (
        derive_query_traits(query).is_cross_domain_impact
    )


def _choose_coverage_frontier_variant(
    query: str,
    *,
    source_route: str,
) -> tuple[str, str] | None:
    if source_route != "policy":
        return None

    variants = build_query_variants(
        query=query,
        route_label="mixed",
        primary_route="policy",
        supplemental_route="industry",
        target_route="industry",
        variant_limit=5,
    )
    candidates = [
        variant
        for variant in variants
        if variant.reason_code != "original"
    ]
    if not candidates:
        return None
    selected = min(
        candidates,
        key=lambda variant: (
            _COVERAGE_FRONTIER_VARIANT_PRIORITY.get(variant.reason_code, 99),
            len(variant.query),
            variant.query,
        ),
    )
    return selected.query, selected.reason_code


def _query_requests_multiple_academic_items(query: str) -> bool:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    return any(
        (marker in tokens) if marker.isascii() else (marker in normalized)
        for marker in _ACADEMIC_LIST_INTENT_MARKERS
    )


def _desired_academic_lookup_items(query: str) -> int:
    return 3 if _query_requests_multiple_academic_items(query) else 2


def _academic_lookup_candidate_limit(query: str) -> int:
    return 5 if _query_requests_multiple_academic_items(query) else 2


def _select_academic_lookup_matches(
    query: str,
    *match_groups: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...],
) -> tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...]:
    desired_limit = _desired_academic_lookup_items(query)
    combined_matches = _combine_ranked_matches(
        *match_groups,
        limit=_academic_lookup_candidate_limit(query),
    )
    if desired_limit <= 2 or len(combined_matches) <= 2:
        return combined_matches[:desired_limit]

    best_alignment = _partial_match_alignment_score(query, combined_matches[0][0])
    selected = list(combined_matches[:2])
    for record, matched_slice, slice_overlap in combined_matches[2:]:
        if not _academic_fast_path_match_allowed(
            query,
            record=record,
            matched_slice=matched_slice,
            slice_overlap=slice_overlap,
        ):
            continue
        if not _should_surface_additional_partial_match(
            query,
            record,
            best_alignment=best_alignment,
        ):
            continue
        selected.append((record, matched_slice, slice_overlap))
        if len(selected) >= desired_limit:
            break
    return tuple(selected)


def _should_attempt_same_route_enrichment(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    local_candidate: AnswerResponse | None,
) -> bool:
    if retrieval_response.status != "success" or retrieval_response.failure_reason is not None:
        return False
    if retrieval_response.gaps or not canonical_evidence:
        return False
    if retrieval_response.supplemental_route is not None:
        return False
    if local_candidate is None or local_candidate.answer_status != "grounded_success":
        return False
    desired_items = 2
    if (
        retrieval_response.primary_route == "academic"
        and _is_academic_lookup_query(query)
    ):
        desired_items = _desired_academic_lookup_items(query)
    if (
        len(local_candidate.sources) >= desired_items
        or len(local_candidate.key_points) >= desired_items
    ):
        return False

    if retrieval_response.primary_route == "industry":
        return (
            _is_industry_lookup_query(query)
            and derive_query_traits(query).has_trend_intent
        )
    if retrieval_response.primary_route == "academic":
        return (
            _is_academic_lookup_query(query)
            and _query_requests_multiple_academic_items(query)
        )
    return False


def _choose_same_route_enrichment_variant(
    query: str,
    *,
    route: str,
) -> tuple[str, str]:
    variants = build_query_variants(
        query=query,
        route_label=route,  # type: ignore[arg-type]
        primary_route=route,  # type: ignore[arg-type]
        supplemental_route=None,
        target_route=route,  # type: ignore[arg-type]
        variant_limit=5,
    )
    if route == "academic":
        multiple_item_query = _query_requests_multiple_academic_items(query)
        reason_codes = {variant.reason_code for variant in variants}
        prefer_ascii_core = (
            multiple_item_query
            and _query_uses_cjk(query)
            and "academic_ascii_core" in reason_codes
        )
        priority = {
            "academic_ascii_core": (
                0
                if prefer_ascii_core
                else (1 if multiple_item_query else 0)
            ),
            "academic_lookup": (
                1
                if prefer_ascii_core
                else (0 if multiple_item_query else 4)
            ),
            "academic_phrase_locked": 2 if multiple_item_query else 1,
            "academic_evidence_type_focus": 3 if multiple_item_query else 2,
            "academic_topic_focus": 4 if multiple_item_query else 3,
            "academic_benchmark": 5,
            "original": 6,
        }
    else:
        priority = {
            "industry_cjk_gloss": 0,
            "original": 1,
            "core_focus": 2,
            "industry_trend": 3,
            "industry_share": 4,
        }
    selected = min(
        variants,
        key=lambda variant: (
            priority.get(variant.reason_code, 99),
            len(variant.query),
            variant.query,
        ),
    )
    return selected.query, selected.reason_code


def _successful_retrieval_source_ids(
    retrieval_trace: tuple[dict[str, object], ...],
) -> set[str]:
    source_ids: set[str] = set()
    for entry in retrieval_trace:
        source_id = entry.get("source_id")
        hit_count = entry.get("hit_count")
        if isinstance(source_id, str) and isinstance(hit_count, int) and hit_count > 0:
            source_ids.add(source_id)
    return source_ids


def _combine_ranked_matches(
    *match_groups: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...],
    limit: int = 2,
) -> tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...]:
    combined: list[tuple[CanonicalEvidence, EvidenceSlice, int]] = []
    seen_evidence_ids: set[str] = set()
    for group in match_groups:
        for match in group:
            record = match[0]
            if record.evidence_id in seen_evidence_ids:
                continue
            combined.append(match)
            seen_evidence_ids.add(record.evidence_id)
            if len(combined) >= limit:
                return tuple(combined)
    return tuple(combined)


def _should_activate_coverage_frontier(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
) -> bool:
    if retrieval_response.route_label == "mixed":
        return False
    if retrieval_response.primary_route != "policy":
        return False
    if retrieval_response.supplemental_route is not None:
        return False
    if retrieval_response.status != "success" or retrieval_response.failure_reason is not None:
        return False
    if retrieval_response.gaps or not canonical_evidence:
        return False
    if not _is_cross_domain_effect_query(query):
        return False

    query_terms = _content_terms(query)
    primary_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="policy",
        route_role="primary",
        limit=1,
    )
    return bool(
        primary_matches
        and primary_matches[0][2] >= min(2, len(query_terms))
    )


def _coverage_frontier_trace_entry(
    *,
    stage: str,
    probe: CoverageFrontierProbe,
    started_at_ms: int,
    elapsed_ms: int,
    hit_count: int,
    failure_reason: RetrievalFailureReason | None,
    error_class: str,
    probe_variant_reason_code: str,
) -> dict[str, object]:
    return {
        "source_id": probe.source_id,
        "stage": stage,
        "started_at_ms": started_at_ms,
        "elapsed_ms": elapsed_ms,
        "hit_count": hit_count,
        "failure_reason": failure_reason,
        "gaps": [] if failure_reason is None else [probe.source_id],
        "error_class": error_class,
        "planner_backup_source_id": None,
        "was_cancelled_by_deadline": False,
        "probe_query": probe.probe_query,
        "probe_reason_code": probe.reason_code,
        "probe_variant_reason_code": probe_variant_reason_code,
        "source_route": probe.source_route,
        "target_route": probe.target_route,
        "alignment_score": probe.alignment_score,
        "selected_evidence_id": probe.selected_evidence_id,
        "selected_title": probe.selected_title,
        "selected_url": probe.selected_url,
    }


def _coverage_frontier_hit_is_duplicate(
    hit: RetrievalHit,
    *,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> bool:
    normalized_title = normalize_query_text(hit.title)
    normalized_url = hit.url.strip().lower()
    normalized_doi = normalize_query_text(hit.doi) if hit.doi else ""
    normalized_arxiv_id = normalize_query_text(hit.arxiv_id) if hit.arxiv_id else ""

    for record in canonical_evidence:
        if normalized_url and normalized_url == record.canonical_url.strip().lower():
            return True
        if normalized_title and normalized_title == normalize_query_text(
            record.canonical_title
        ):
            return True
        if normalized_doi and record.doi and normalized_doi == normalize_query_text(
            record.doi
        ):
            return True
        if (
            normalized_arxiv_id
            and record.arxiv_id
            and normalized_arxiv_id == normalize_query_text(record.arxiv_id)
        ):
            return True
    return False


def _select_coverage_frontier_hit(
    probe: CoverageFrontierProbe,
    *,
    query: str,
    probe_hits: list[RetrievalHit],
    canonical_evidence: tuple[CanonicalEvidence, ...] = (),
) -> tuple[CoverageFrontierProbe, RetrievalHit | None, int]:
    ranked_hits = list(
        prioritize_hits(
            probe.target_route,
            [
                replace(
                    hit,
                    target_route=probe.target_route,
                    variant_reason_codes=(probe.reason_code,),
                    variant_queries=(probe.probe_query,),
                )
                for hit in probe_hits
            ],
            primary_route=probe.target_route,
            supplemental_route=None,
            query=probe.probe_query,
        )
    )
    best_probe = probe
    best_hit: RetrievalHit | None = None
    best_key = (-1, "", "", "", "")

    for hit in ranked_hits:
        if canonical_evidence and _coverage_frontier_hit_is_duplicate(
            hit,
            canonical_evidence=canonical_evidence,
        ):
            continue
        original_query_probe = attach_probe_alignment(
            probe,
            query=query,
            hit=hit,
        )
        probe_query_alignment = score_query_alignment(
            probe.probe_query,
            route=probe.target_route,
            title=hit.title,
            snippet=hit.snippet,
            url=hit.url,
            authority=hit.authority,
            publication_date=hit.publication_date,
            effective_date=hit.effective_date,
            version=hit.version,
            year=hit.year,
        )
        candidate_probe = replace(
            original_query_probe,
            alignment_score=max(
                original_query_probe.alignment_score,
                probe_query_alignment,
            ),
        )
        candidate_key = (
            candidate_probe.alignment_score,
            candidate_probe.selected_evidence_id or "",
            candidate_probe.selected_title or "",
            candidate_probe.selected_url or "",
            hit.source_id,
        )
        if candidate_key > best_key:
            best_key = candidate_key
            best_probe = candidate_probe
            best_hit = hit

    if best_hit is None or best_probe.alignment_score <= 0:
        return probe, None, len(ranked_hits)
    return best_probe, best_hit, len(ranked_hits)


def _merge_coverage_frontier_evidence(
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    supplemental_hits: tuple[RetrievalHit, ...],
    runtime_budget: RuntimeBudget,
) -> tuple[tuple[CanonicalEvidence, ...], bool, bool, bool]:
    if not supplemental_hits:
        return canonical_evidence, False, False, False

    supplemental_records = score_evidence_records(
        collapse_evidence_records(
            normalize_hit_candidates(
                supplemental_hits,
                route_role_by_source={
                    hit.source_id: "supplemental" for hit in supplemental_hits
                },
                route_role_by_target_route={
                    hit.target_route: "supplemental"
                    for hit in supplemental_hits
                    if hit.target_route is not None
                },
            )
        )
    )
    combined_pack = build_evidence_pack(
        score_evidence_records([*canonical_evidence, *supplemental_records]),
        token_budget=runtime_budget.evidence_token_budget,
        top_k=DEFAULT_EVIDENCE_TOP_K,
        supplemental_min_items=DEFAULT_SUPPLEMENTAL_MIN_ITEMS,
    )
    has_supplemental_evidence = any(
        record.route_role == "supplemental"
        for record in combined_pack.canonical_evidence
    )
    return (
        combined_pack.canonical_evidence,
        combined_pack.clipped,
        combined_pack.pruned,
        has_supplemental_evidence,
    )


def _build_same_route_academic_enrichment_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
) -> AnswerResponse | None:
    candidate_limit = _academic_lookup_candidate_limit(query)
    primary_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="academic",
        route_role="primary",
        limit=candidate_limit,
    )
    supplemental_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="academic",
        route_role="supplemental",
        limit=candidate_limit,
    )
    combined_matches = _select_academic_lookup_matches(
        query,
        primary_matches,
        supplemental_matches,
    )
    if len(combined_matches) <= 1:
        return None
    if not _academic_fast_path_match_allowed(
        query,
        record=combined_matches[0][0],
        matched_slice=combined_matches[0][1],
        slice_overlap=combined_matches[0][2],
    ):
        return None
    return _build_academic_lookup_fast_path_response(
        retrieval_response,
        canonical_evidence,
        query=query,
        matched_records=combined_matches,
    )


def _build_same_route_industry_enrichment_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
) -> AnswerResponse | None:
    primary_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="industry",
        route_role="primary",
        limit=2,
    )
    supplemental_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="industry",
        route_role="supplemental",
        limit=2,
    )
    combined_matches = _combine_ranked_matches(
        primary_matches,
        supplemental_matches,
        limit=2,
    )
    query_terms = _content_terms(query)
    if (
        len(combined_matches) <= 1
        or combined_matches[0][2] < min(2, len(query_terms))
    ):
        return None
    return _build_industry_lookup_fast_path_response(
        retrieval_response,
        canonical_evidence,
        query=query,
        matched_record=combined_matches[0][0],
        matched_slice=combined_matches[0][1],
        supporting_matches=combined_matches[1:],
    )


async def _maybe_apply_same_route_enrichment(
    *,
    query: str,
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    local_fast_path_response: AnswerResponse,
    adapter_registry: Mapping[str, Adapter],
    runtime_budget: RuntimeBudget,
    retrieval_elapsed_seconds: float,
    retrieval_trace: tuple[dict[str, object], ...],
) -> tuple[
    RetrieveResponse,
    tuple[CanonicalEvidence, ...],
    tuple[dict[str, object], ...],
    float,
    AnswerResponse | None,
]:
    if not _should_attempt_same_route_enrichment(
        retrieval_response,
        canonical_evidence,
        query=query,
        local_candidate=local_fast_path_response,
    ):
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    probe_query, probe_variant_reason_code = _choose_same_route_enrichment_variant(
        query,
        route=retrieval_response.primary_route,
    )
    remaining_request_seconds = runtime_budget.remaining_request_seconds(
        elapsed_seconds=retrieval_elapsed_seconds,
    )
    if not has_budget_for_coverage_frontier_probe(
        remaining_request_seconds=remaining_request_seconds,
    ):
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    used_source_ids = _successful_retrieval_source_ids(retrieval_trace)
    frontier_candidates = tuple(
        replace(
            candidate,
            reason_code=(
                f"{candidate.reason_code}:{probe_variant_reason_code}"
            ),
        )
        for candidate in build_coverage_frontier_candidates(
            source_route=retrieval_response.primary_route,
            probe_query=probe_query,
        )
        if candidate.target_route == retrieval_response.primary_route
        and candidate.source_id not in used_source_ids
    )
    if not frontier_candidates:
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    total_probe_elapsed_seconds = 0.0
    updated_trace = list(retrieval_trace)
    selected_hits_by_evidence_id: dict[str, RetrievalHit] = {}
    selected_probes: list[CoverageFrontierProbe] = []
    any_probe_executed = False

    for frontier_probe in frontier_candidates:
        adapter = adapter_registry.get(frontier_probe.source_id)
        if adapter is None:
            continue

        current_remaining_seconds = runtime_budget.remaining_request_seconds(
            elapsed_seconds=retrieval_elapsed_seconds + total_probe_elapsed_seconds,
        )
        if not has_budget_for_coverage_frontier_probe(
            remaining_request_seconds=current_remaining_seconds,
        ):
            break

        probe_timeout_seconds = min(
            COVERAGE_FRONTIER_PER_PROBE_TIMEOUT_SECONDS,
            current_remaining_seconds
            - COVERAGE_FRONTIER_MIN_REMAINING_SECONDS_TO_PROBE,
        )
        if probe_timeout_seconds <= 0:
            break
        if runtime_budget.remaining_synthesis_seconds(
            retrieval_elapsed_seconds=(
                retrieval_elapsed_seconds
                + total_probe_elapsed_seconds
                + probe_timeout_seconds
            ),
        ) <= 0.5:
            break

        any_probe_executed = True
        probe_started_at = time.perf_counter()
        failure_reason: RetrievalFailureReason | None = None
        error_class = "ok"
        try:
            probe_hits = await asyncio.wait_for(
                adapter(frontier_probe.probe_query),
                timeout=probe_timeout_seconds,
            )
        except TimeoutError:
            failure_reason = "timeout"
            error_class = "timeout"
            probe_hits = []
        except Exception:
            failure_reason = "adapter_error"
            error_class = "adapter_error"
            probe_hits = []
        probe_elapsed_seconds = time.perf_counter() - probe_started_at
        total_probe_elapsed_seconds += probe_elapsed_seconds

        annotated_probe = frontier_probe
        if probe_hits:
            annotated_probe, selected_hit, _ = _select_coverage_frontier_hit(
                frontier_probe,
                query=query,
                probe_hits=probe_hits,
                canonical_evidence=canonical_evidence,
            )
            if (
                selected_hit is not None
                and annotated_probe.selected_evidence_id is not None
            ):
                selected_hits_by_evidence_id[annotated_probe.selected_evidence_id] = (
                    selected_hit
                )
                selected_probes.append(annotated_probe)
        if failure_reason is None and annotated_probe.selected_evidence_id is None:
            failure_reason = "no_hits"
            error_class = "parse_empty"

        updated_trace.append(
            _coverage_frontier_trace_entry(
                stage="coverage_frontier_probe",
                probe=annotated_probe,
                started_at_ms=int(
                    round(
                        (
                            retrieval_elapsed_seconds
                            + total_probe_elapsed_seconds
                            - probe_elapsed_seconds
                        )
                        * 1000
                    )
                ),
                elapsed_ms=int(round(probe_elapsed_seconds * 1000)),
                hit_count=len(probe_hits),
                failure_reason=failure_reason,
                error_class=error_class,
                probe_variant_reason_code=probe_variant_reason_code,
            )
        )

    if not any_probe_executed:
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    winner = select_coverage_frontier_winner(tuple(selected_probes))
    if winner is None or winner.selected_evidence_id is None:
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )

    selected_hit = selected_hits_by_evidence_id.get(winner.selected_evidence_id)
    if selected_hit is None:
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )

    merged_evidence, clipped, pruned, has_supplemental_evidence = _merge_coverage_frontier_evidence(
        canonical_evidence,
        supplemental_hits=(selected_hit,),
        runtime_budget=runtime_budget,
    )
    if not has_supplemental_evidence:
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )

    updated_response = retrieval_response.model_copy(
        update={
            "supplemental_route": retrieval_response.primary_route,
            "evidence_clipped": retrieval_response.evidence_clipped or clipped,
            "evidence_pruned": retrieval_response.evidence_pruned or pruned,
        }
    )
    if retrieval_response.primary_route == "academic":
        enriched_response = _build_same_route_academic_enrichment_response(
            updated_response,
            merged_evidence,
            query=query,
        )
    else:
        enriched_response = _build_same_route_industry_enrichment_response(
            updated_response,
            merged_evidence,
            query=query,
        )
    if enriched_response is None:
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )
    if (
        len(enriched_response.sources) <= len(local_fast_path_response.sources)
        and len(enriched_response.key_points) <= len(local_fast_path_response.key_points)
    ):
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )
    return (
        updated_response,
        merged_evidence,
        tuple(updated_trace),
        total_probe_elapsed_seconds,
        enriched_response,
    )


async def _maybe_apply_coverage_frontier_policy(
    *,
    query: str,
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    adapter_registry: Mapping[str, Adapter],
    runtime_budget: RuntimeBudget,
    retrieval_elapsed_seconds: float,
    retrieval_trace: tuple[dict[str, object], ...],
) -> tuple[
    RetrieveResponse,
    tuple[CanonicalEvidence, ...],
    tuple[dict[str, object], ...],
    float,
    AnswerResponse | None,
]:
    if not _should_activate_coverage_frontier(
        retrieval_response,
        canonical_evidence,
        query=query,
    ):
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    selected_variant = _choose_coverage_frontier_variant(
        query,
        source_route=retrieval_response.primary_route,
    )
    if selected_variant is None:
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None
    probe_query, probe_variant_reason_code = selected_variant

    remaining_request_seconds = runtime_budget.remaining_request_seconds(
        elapsed_seconds=retrieval_elapsed_seconds,
    )
    if not has_budget_for_coverage_frontier_probe(
        remaining_request_seconds=remaining_request_seconds,
    ):
        early_response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason=(
                "remaining request budget was below the minimum required for "
                "complementary coverage probing."
            ),
        )
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, early_response

    frontier_candidates = tuple(
        replace(
            candidate,
            reason_code=(
                f"{candidate.reason_code}:{probe_variant_reason_code}"
            ),
        )
        for candidate in build_coverage_frontier_candidates(
            source_route=retrieval_response.primary_route,
            probe_query=probe_query,
        )
    )
    if not frontier_candidates:
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    total_probe_elapsed_seconds = 0.0
    total_candidate_hit_count = 0
    updated_trace = list(retrieval_trace)
    selected_hits_by_evidence_id: dict[str, RetrievalHit] = {}
    selected_probes: list[CoverageFrontierProbe] = []
    any_probe_executed = False

    for frontier_probe in frontier_candidates:
        adapter = adapter_registry.get(frontier_probe.source_id)
        if adapter is None:
            continue

        current_remaining_seconds = runtime_budget.remaining_request_seconds(
            elapsed_seconds=retrieval_elapsed_seconds + total_probe_elapsed_seconds,
        )
        if not has_budget_for_coverage_frontier_probe(
            remaining_request_seconds=current_remaining_seconds,
        ):
            break

        probe_timeout_seconds = min(
            COVERAGE_FRONTIER_PER_PROBE_TIMEOUT_SECONDS,
            current_remaining_seconds
            - COVERAGE_FRONTIER_MIN_REMAINING_SECONDS_TO_PROBE,
        )
        if probe_timeout_seconds <= 0:
            break
        if runtime_budget.remaining_synthesis_seconds(
            retrieval_elapsed_seconds=(
                retrieval_elapsed_seconds
                + total_probe_elapsed_seconds
                + probe_timeout_seconds
            ),
        ) <= 0.5:
            break

        any_probe_executed = True
        probe_started_at = time.perf_counter()
        failure_reason: RetrievalFailureReason | None = None
        error_class = "ok"
        try:
            probe_hits = await asyncio.wait_for(
                adapter(frontier_probe.probe_query),
                timeout=probe_timeout_seconds,
            )
        except TimeoutError:
            failure_reason = "timeout"
            error_class = "timeout"
            probe_hits = []
        except Exception:
            failure_reason = "adapter_error"
            error_class = "adapter_error"
            probe_hits = []
        probe_elapsed_seconds = time.perf_counter() - probe_started_at
        total_probe_elapsed_seconds += probe_elapsed_seconds

        annotated_probe = frontier_probe
        if probe_hits:
            annotated_probe, selected_hit, candidate_hit_count = _select_coverage_frontier_hit(
                frontier_probe,
                query=query,
                probe_hits=probe_hits,
                canonical_evidence=canonical_evidence,
            )
            total_candidate_hit_count += candidate_hit_count
            if selected_hit is not None and annotated_probe.selected_evidence_id is not None:
                selected_hits_by_evidence_id[annotated_probe.selected_evidence_id] = selected_hit
                selected_probes.append(annotated_probe)
        else:
            selected_hit = None
        if failure_reason is None and annotated_probe.selected_evidence_id is None:
            failure_reason = "no_hits"
            error_class = "parse_empty"

        updated_trace.append(
            _coverage_frontier_trace_entry(
                stage="coverage_frontier_probe",
                probe=annotated_probe,
                started_at_ms=int(
                    round(
                        (retrieval_elapsed_seconds + total_probe_elapsed_seconds - probe_elapsed_seconds)
                        * 1000
                    )
                ),
                elapsed_ms=int(round(probe_elapsed_seconds * 1000)),
                hit_count=len(probe_hits),
                failure_reason=failure_reason,
                error_class=error_class,
                probe_variant_reason_code=probe_variant_reason_code,
            )
        )

    if not any_probe_executed:
        return retrieval_response, canonical_evidence, retrieval_trace, 0.0, None

    winner = select_coverage_frontier_winner(tuple(selected_probes))
    if winner is None:
        early_response = _build_coverage_frontier_insufficient_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="no aligned complementary evidence emerged from the bounded coverage frontier.",
        )
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            early_response,
        )

    ambiguous_frontier = (
        len(selected_probes) > 1
        or total_candidate_hit_count > len(selected_probes)
    )
    augmented_hits = (
        (selected_hits_by_evidence_id[winner.selected_evidence_id],)
        if ambiguous_frontier and winner.selected_evidence_id is not None
        else tuple(
            selected_hits_by_evidence_id[probe.selected_evidence_id]
            for probe in selected_probes
            if probe.selected_evidence_id is not None
            and probe.selected_evidence_id in selected_hits_by_evidence_id
        )
    )
    merged_evidence, clipped, pruned, has_supplemental_evidence = _merge_coverage_frontier_evidence(
        canonical_evidence,
        supplemental_hits=augmented_hits,
        runtime_budget=runtime_budget,
    )
    if not has_supplemental_evidence:
        early_response = _build_coverage_frontier_insufficient_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="frontier probe hits were not retained after evidence packing.",
        )
        return (
            retrieval_response,
            canonical_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            early_response,
        )

    updated_response = retrieval_response.model_copy(
        update={
            "supplemental_route": winner.target_route,
            "evidence_clipped": retrieval_response.evidence_clipped or clipped,
            "evidence_pruned": retrieval_response.evidence_pruned or pruned,
        }
    )
    local_candidate = _build_local_answer_candidate(
        updated_response,
        merged_evidence,
        query=query,
        require_clean_runtime=True,
    )
    local_grounded = (
        local_candidate is not None
        and local_candidate.answer_status == "grounded_success"
    )

    decision = (
        "deepen"
        if ambiguous_frontier
        else decide_coverage_frontier_sufficiency(
            has_grounded_local_answer=local_grounded,
            aligned_supplemental_evidence_count=(
                len(selected_probes) if local_grounded else 0
            ),
            winner=winner,
        )
    )
    if decision == "grounded_success":
        return (
            updated_response,
            merged_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )
    if decision != "deepen" or winner.selected_evidence_id is None:
        early_response = _build_coverage_frontier_insufficient_response(
            updated_response,
            merged_evidence,
            query=query,
            reason="bounded coverage frontier did not establish enough grounded complementary support.",
        )
        return (
            updated_response,
            merged_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            early_response,
        )

    updated_trace.append(
        _coverage_frontier_trace_entry(
            stage="coverage_frontier_deepen",
            probe=winner,
            started_at_ms=int(
                round(
                    (retrieval_elapsed_seconds + total_probe_elapsed_seconds) * 1000
                )
            ),
            elapsed_ms=0,
            hit_count=1,
            failure_reason=None,
            error_class="ok",
            probe_variant_reason_code=probe_variant_reason_code,
        )
    )
    local_candidate = _build_local_answer_candidate(
        updated_response,
        merged_evidence,
        query=query,
        require_clean_runtime=True,
    )
    if local_candidate is not None and local_candidate.answer_status == "grounded_success":
        return (
            updated_response,
            merged_evidence,
            tuple(updated_trace),
            total_probe_elapsed_seconds,
            None,
        )

    early_response = _build_coverage_frontier_insufficient_response(
        updated_response,
        merged_evidence,
        query=query,
        reason="bounded deepen on the best frontier branch still could not ground the answer.",
    )
    return (
        updated_response,
        merged_evidence,
        tuple(updated_trace),
        total_probe_elapsed_seconds,
        early_response,
    )


def _best_policy_lookup_record(
    query: str,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> CanonicalEvidence | None:
    traits = derive_query_traits(query)
    needs_version = traits.has_version_intent
    needs_effective_date = traits.has_effective_date_intent
    needs_policy_change = traits.is_policy_change

    best_record: CanonicalEvidence | None = None
    best_candidate = (-1, -1, -1, -1, "", "", "")
    for record in canonical_evidence:
        if record.domain != "policy" or not record.retained_slices:
            continue

        has_version = int(record.version_status == "observed" and record.version is not None)
        has_effective_date = int(record.effective_date is not None)
        alignment_score = score_query_alignment(
            query,
            route="policy",
            title=record.canonical_title,
            snippet=" ".join(slice_.text for slice_ in record.retained_slices),
            url=record.canonical_url,
            authority=record.authority,
            publication_date=record.publication_date,
            effective_date=record.effective_date,
            version=record.version,
            year=record.year,
        )
        candidate = (
            has_version if needs_version else 1,
            has_effective_date if needs_effective_date else 1,
            int(alignment_score > 0) if needs_policy_change else 1,
            alignment_score,
            record.publication_date or "",
            record.effective_date or "",
            record.evidence_id,
        )
        if candidate > best_candidate:
            best_candidate = candidate
            best_record = record

    if best_record is None:
        return None
    if needs_version and not (
        best_record.version_status == "observed" and best_record.version is not None
    ):
        return None
    if needs_effective_date and best_record.effective_date is None:
        return None
    if needs_policy_change:
        alignment_score = score_query_alignment(
            query,
            route="policy",
            title=best_record.canonical_title,
            snippet=" ".join(slice_.text for slice_ in best_record.retained_slices),
            url=best_record.canonical_url,
            authority=best_record.authority,
            publication_date=best_record.publication_date,
            effective_date=best_record.effective_date,
            version=best_record.version,
            year=best_record.year,
        )
        if alignment_score <= 0:
            return None
    return best_record


def _has_query_evidence_overlap(
    query: str,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    primary_route: str,
) -> bool:
    query_terms = _content_terms(query)
    if not query_terms:
        return True

    evidence_terms: set[str] = set()
    max_slice_overlap, _, _ = _best_slice_overlap(query_terms, canonical_evidence)
    for record in canonical_evidence:
        evidence_terms.update(_content_terms(record.canonical_title))
        for slice_ in record.retained_slices:
            evidence_terms.update(_content_terms(slice_.text))

    overlap_count = len(query_terms & evidence_terms)
    if primary_route == "academic":
        required_slice_overlap = min(2, len(query_terms))
        return max_slice_overlap >= required_slice_overlap

    required_overlap = min(2, len(query_terms))
    return overlap_count >= required_overlap


def _rehydrate_canonical_evidence(
    item: RetrieveCanonicalEvidenceItem,
) -> CanonicalEvidence:
    best_slice = item.retained_slices[0] if item.retained_slices else None
    snippet = best_slice.text if best_slice is not None else item.canonical_title
    source_id = (
        best_slice.source_record_id
        if best_slice is not None
        else f"{item.domain}_canonical_source"
    )
    raw_hit = RetrievalHit(
        source_id=source_id,
        title=item.canonical_title,
        url=item.canonical_url,
        snippet=snippet,
        credibility_tier=None,
        authority=item.authority,
        jurisdiction=item.jurisdiction,
        publication_date=item.publication_date,
        effective_date=item.effective_date,
        version=item.version,
        doi=item.doi,
        arxiv_id=item.arxiv_id,
        first_author=item.first_author,
        year=item.year,
        evidence_level=item.evidence_level,
    )
    raw_record = RawEvidenceRecord(
        source_id=raw_hit.source_id,
        title=raw_hit.title,
        url=raw_hit.url,
        snippet=raw_hit.snippet,
        credibility_tier=raw_hit.credibility_tier,
        route_role=item.route_role,
        token_estimate=_estimate_tokens(raw_hit.snippet),
        raw_hit=raw_hit,
        authority=item.authority,
        jurisdiction=item.jurisdiction,
        jurisdiction_status=item.jurisdiction_status,
        publication_date=item.publication_date,
        effective_date=item.effective_date,
        version=item.version,
        version_status=item.version_status,
        evidence_level=item.evidence_level,
        canonical_match_confidence=item.canonical_match_confidence,
        doi=item.doi,
        arxiv_id=item.arxiv_id,
        first_author=item.first_author,
        year=item.year,
    )
    return CanonicalEvidence(
        evidence_id=item.evidence_id,
        domain=item.domain,
        canonical_title=item.canonical_title,
        canonical_url=item.canonical_url,
        raw_records=(raw_record,),
        retained_slices=tuple(
            EvidenceSlice(
                text=slice_.text,
                source_record_id=slice_.source_record_id,
                source_span=slice_.source_span,
                score=0.0,
                token_estimate=_estimate_tokens(slice_.text),
            )
            for slice_ in item.retained_slices
        ),
        linked_variants=tuple(
            LinkedVariant(
                source_id=variant.source_id,
                title=variant.title,
                url=variant.url,
                variant_type=variant.variant_type,
                canonical_match_confidence=variant.canonical_match_confidence,
                doi=variant.doi,
                arxiv_id=variant.arxiv_id,
                first_author=variant.first_author,
                year=variant.year,
            )
            for variant in item.linked_variants
        ),
        authority=item.authority,
        jurisdiction=item.jurisdiction,
        jurisdiction_status=item.jurisdiction_status,
        publication_date=item.publication_date,
        effective_date=item.effective_date,
        version=item.version,
        version_status=item.version_status,
        evidence_level=item.evidence_level,
        canonical_match_confidence=item.canonical_match_confidence,
        doi=item.doi,
        arxiv_id=item.arxiv_id,
        first_author=item.first_author,
        year=item.year,
        route_role=item.route_role,
    )


def _dedupe_sources(
    cited_evidence_ids: list[str],
    draft_sources: list[object],
    evidence_by_id: dict[str, CanonicalEvidence],
) -> list[dict[str, str]]:
    sources_by_id: dict[str, object] = {
        source.evidence_id: source for source in draft_sources
    }
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for evidence_id in cited_evidence_ids:
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        source = sources_by_id.get(evidence_id)
        if source is not None:
            deduped.append(
                {
                    "evidence_id": source.evidence_id,
                    "title": source.title,
                    "url": source.url,
                }
            )
            continue

        record = evidence_by_id[evidence_id]
        deduped.append(
            {
                "evidence_id": record.evidence_id,
                "title": record.canonical_title,
                "url": record.canonical_url,
            }
        )
    return deduped


def _truncate_words(text: str, *, max_words: int = 18) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip().rstrip(",.;:") + "..."


def _partial_match_alignment_score(query: str, record: CanonicalEvidence) -> int:
    return score_query_alignment(
        query,
        route=record.domain,  # type: ignore[arg-type]
        title=record.canonical_title,
        snippet=" ".join(slice_.text for slice_ in record.retained_slices),
        url=record.canonical_url,
        authority=record.authority,
        publication_date=record.publication_date,
        effective_date=record.effective_date,
        version=record.version,
        year=record.year,
    )


def _partial_extra_match_threshold(best_alignment: int) -> int:
    if best_alignment <= 0:
        return 0
    return max(8, int(best_alignment * 0.65 + 0.999))


def _partial_match_focus_overlap(query: str, record: CanonicalEvidence) -> int:
    query_terms = set(_content_terms(query))
    if record.domain == "industry":
        gloss_query = _build_industry_cjk_gloss_query(query)
        if gloss_query:
            query_terms.update(_content_terms(gloss_query))
    if not query_terms:
        return 0

    record_terms = set(_content_terms(record.canonical_title))
    for slice_ in record.retained_slices:
        record_terms.update(_content_terms(slice_.text))
    return len(query_terms & record_terms)


def _should_surface_additional_partial_match(
    query: str,
    record: CanonicalEvidence,
    *,
    best_alignment: int,
) -> bool:
    if best_alignment <= 0:
        return False
    if record.domain == "industry" and _industry_thematic_overlap(query, record) <= 0:
        return False
    query_terms = set(_content_terms(query))
    if record.domain == "industry":
        gloss_query = _build_industry_cjk_gloss_query(query)
        if gloss_query:
            query_terms.update(_content_terms(gloss_query))
    required_focus_overlap = min(2, len(query_terms))
    if required_focus_overlap > 0 and _partial_match_focus_overlap(query, record) < required_focus_overlap:
        return False
    return _partial_match_alignment_score(query, record) >= _partial_extra_match_threshold(
        best_alignment
    )


def _partition_industry_supporting_matches(
    query: str,
    primary_record: CanonicalEvidence,
    supporting_matches: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...],
) -> tuple[
    tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...],
    tuple[CanonicalEvidence, EvidenceSlice, int] | None,
]:
    if not supporting_matches:
        return (), None

    best_alignment = _partial_match_alignment_score(query, primary_record)
    direct_matches: list[tuple[CanonicalEvidence, EvidenceSlice, int]] = []
    contextual_match: tuple[CanonicalEvidence, EvidenceSlice, int] | None = None

    for match in supporting_matches:
        record, _, _ = match
        if _should_surface_additional_partial_match(
            query,
            record,
            best_alignment=best_alignment,
        ):
            direct_matches.append(match)
            continue
        if (
            contextual_match is None
            and _industry_thematic_overlap(query, record) > 0
            and _partial_match_alignment_score(query, record) > 0
        ):
            contextual_match = match

    return tuple(direct_matches), contextual_match


def _select_partial_evidence_matches(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    limit: int = 2,
) -> tuple[tuple[CanonicalEvidence, EvidenceSlice], ...]:
    selected: list[tuple[CanonicalEvidence, EvidenceSlice]] = []
    seen_evidence_ids: set[str] = set()

    def _append_match(
        record: CanonicalEvidence | None,
        slice_: EvidenceSlice | None,
    ) -> None:
        if record is None or slice_ is None:
            return
        if record.evidence_id in seen_evidence_ids:
            return
        seen_evidence_ids.add(record.evidence_id)
        selected.append((record, slice_))

    if (
        retrieval_response.route_label == "mixed"
        and retrieval_response.supplemental_route is not None
    ):
        primary_matches = _top_route_matches(
            query,
            canonical_evidence,
            domain=retrieval_response.primary_route,
            route_role="primary",
            limit=1,
        )
        supplemental_matches = _top_route_matches(
            query,
            canonical_evidence,
            domain=retrieval_response.supplemental_route,
            route_role="supplemental",
            limit=1,
        )
        if primary_matches:
            _append_match(primary_matches[0][0], primary_matches[0][1])
        if supplemental_matches:
            _append_match(supplemental_matches[0][0], supplemental_matches[0][1])

    route_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain=retrieval_response.primary_route,
        route_role="primary",
        limit=limit,
    )
    best_route_alignment = (
        _partial_match_alignment_score(query, route_matches[0][0]) if route_matches else 0
    )
    for index, (record, slice_, _) in enumerate(route_matches):
        if len(selected) >= limit:
            break
        if index > 0 and not _should_surface_additional_partial_match(
            query,
            record,
            best_alignment=best_route_alignment,
        ):
            continue
        _append_match(record, slice_)

    if len(selected) < limit:
        best_alignment = 0
        if canonical_evidence:
            best_alignment = max(
                _partial_match_alignment_score(query, record)
                for record in canonical_evidence
            )
        for record in canonical_evidence:
            if not record.retained_slices or record.evidence_id in seen_evidence_ids:
                continue
            if selected and not _should_surface_additional_partial_match(
                query,
                record,
                best_alignment=best_alignment,
            ):
                continue
            _append_match(record, record.retained_slices[0])
            if len(selected) >= limit:
                break

    return tuple(selected[:limit])


def _build_key_points_from_partial_matches(
    matches: tuple[tuple[CanonicalEvidence, EvidenceSlice], ...],
) -> list[dict[str, object]]:
    key_points: list[dict[str, object]] = []
    for index, (record, slice_) in enumerate(matches, start=1):
        key_points.append(
            {
                "key_point_id": f"kp-{index}",
                "statement": slice_.text,
                "citations": [
                    {
                        "evidence_id": record.evidence_id,
                        "source_record_id": slice_.source_record_id,
                        "source_url": record.canonical_url,
                        "quote_text": slice_.text,
                    }
                ],
            }
        )
    return key_points


def _format_series(items: tuple[str, ...] | list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _format_cjk_series(items: tuple[str, ...] | list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]}和{values[1]}"
    return "、".join(values[:-1]) + f"，以及{values[-1]}"


def _format_quoted_titles(titles: tuple[str, ...] | list[str]) -> str:
    return _format_series([f'"{title}"' for title in titles if title])


def _partial_query_requirements(
    query: str,
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> tuple[str, ...]:
    normalized = normalize_query_text(query)
    tokens = set(query_tokens(normalized))
    traits = derive_query_traits(query)
    use_cjk = _query_uses_cjk(query)
    has_academic = any(record.domain == "academic" for record in canonical_evidence)
    has_industry = any(record.domain == "industry" for record in canonical_evidence)
    has_policy = any(record.domain == "policy" for record in canonical_evidence)

    if retrieval_response.route_label == "mixed":
        return (
            ("政策变化如何传导到供应链投资、支出类别或时间节奏",)
            if use_cjk
            else ("how the policy signal changes suppliers, spending categories, or timelines",)
        )
    if has_industry and (
        "share" in tokens or "market share" in normalized or "份额" in normalized or "市占率" in normalized
    ):
        return (
            (
                "玩家层面的份额或情景",
                "对齐的预测时间范围",
                "细分市场或地区覆盖",
            )
            if use_cjk
            else (
                "player-level shares or scenarios",
                "an aligned forecast horizon",
                "segment or regional coverage",
            )
        )
    if has_industry and traits.has_trend_intent:
        return (
            (
                "量化预测或区间",
                "细分市场或地区拆分",
                "支撑该展望的假设或瓶颈",
            )
            if use_cjk
            else (
                "a numeric forecast or range",
                "segment or regional breakdown",
                "the assumptions or bottlenecks behind the outlook",
            )
        )
    if has_academic and _query_contains_marker(query, _ACADEMIC_BENCHMARK_MARKERS):
        return (
            (
                "基准任务或数据集",
                "指标或基线",
                "可对比的更多 benchmark 论文",
            )
            if use_cjk
            else (
                "benchmark tasks or datasets",
                "metrics or baselines",
                "additional benchmark papers for comparison",
            )
        )
    if has_academic and _query_requests_multiple_academic_items(query):
        return (
            (
                "更多高度相关的论文",
                "期刊/会议或标识信息",
                "每篇论文为何相关的简短说明",
            )
            if use_cjk
            else (
                "more closely related papers",
                "venue or identifier details",
                "brief notes on why each paper matters",
            )
        )
    if has_policy and (
        traits.has_effective_date_intent
        or traits.has_version_intent
        or traits.is_policy_change
    ):
        return (
            ("关键条款或适用范围", "影响对象", "实际合规步骤")
            if use_cjk
            else ("the key clauses or scope", "who is affected", "practical compliance steps")
        )
    return ()


def _partial_missing_summary(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    citation_issues: tuple[str, ...] = (),
    reason: str | None = None,
    use_cjk: bool = False,
) -> str:
    has_academic = any(record.domain == "academic" for record in canonical_evidence)
    has_industry = any(record.domain == "industry" for record in canonical_evidence)

    fragments: list[str] = []
    if retrieval_response.route_label == "mixed":
        fragments.append(
            "能把政策信号和产业信号直接连接起来的更多证据"
            if use_cjk
            else "more evidence showing how the retained policy and industry signals connect"
        )
    elif has_academic:
        fragments.append("更多学术佐证或 benchmark 细节" if use_cjk else "more academic corroboration or benchmark detail")
    elif has_industry:
        fragments.append("更多行业佐证或原始来源细节" if use_cjk else "more industry corroboration or original-source detail")
    else:
        fragments.append("更多交叉佐证" if use_cjk else "more corroborating evidence")

    if citation_issues:
        fragments.append("每个结论都能直接对应来源原文" if use_cjk else "direct source support for every claim")
    if reason:
        normalized_reason = normalize_query_text(reason)
        if "query-specific evidence alignment" in normalized_reason:
            fragments.append("与问题更贴合的直接证据" if use_cjk else "closer query-specific evidence")
        elif "request budget" in normalized_reason or "grounded synthesis" in normalized_reason:
            fragments.append(
                "足够完成完整归因分析的时间"
                if use_cjk
                else "enough time to finish a fully grounded synthesis"
            )
        elif "generation backend" in normalized_reason:
            fragments.append(
                "一次完整的基于来源的综合分析"
                if use_cjk
                else "a completed source-backed synthesis pass"
            )
        else:
            fragments.append(reason.strip().rstrip("."))

    deduped = list(dict.fromkeys(fragment.strip() for fragment in fragments if fragment.strip()))
    if not deduped:
        return "更多交叉佐证" if use_cjk else "more corroborating evidence"
    if len(deduped) == 1:
        return deduped[0]
    if use_cjk:
        return "、".join(deduped[:-1]) + f"，以及{deduped[-1]}"
    return ", ".join(deduped[:-1]) + f", and {deduped[-1]}"


def _build_mixed_partial_bridge_note(
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    use_cjk: bool,
) -> str:
    domains = {record.domain for record in canonical_evidence}
    if "policy" in domains and "industry" in domains:
        if use_cjk:
            return (
                "\u5f53\u524d\u8bc1\u636e\u5df2\u7ecf\u540c\u65f6\u7ed9\u51fa\u4e86\u653f\u7b56"
                "\u4fe1\u53f7\u548c\u540c\u4e3b\u9898\u7684\u4ea7\u4e1a\u4fe1\u53f7\uff0c"
                "\u4f46\u8fd8\u4e0d\u8db3\u4ee5\u786e\u8ba4\u5b8c\u6574\u7684\u5f71\u54cd"
                "\u4f20\u5bfc\u8def\u5f84\u3002"
            )
        return (
            "Current evidence already establishes a regulatory signal and a same-topic "
            "industry signal, but not the transmission path needed for a full impact estimate."
        )
    if "policy" in domains and "academic" in domains:
        if use_cjk:
            return (
                "\u5f53\u524d\u8bc1\u636e\u5df2\u7ecf\u540c\u65f6\u7ed9\u51fa\u4e86\u653f\u7b56"
                "\u4fe1\u53f7\u548c\u540c\u4e3b\u9898\u7684\u7814\u7a76\u4fe1\u53f7\uff0c"
                "\u4f46\u8fd8\u4e0d\u8db3\u4ee5\u786e\u8ba4\u5b8c\u6574\u7684\u5f71\u54cd"
                "\u673a\u5236\u6216\u8303\u56f4\u3002"
            )
        return (
            "Current evidence already establishes a policy signal and a same-topic research "
            "signal, but not the mechanism or scope needed for a full impact estimate."
        )
    if use_cjk:
        return (
            "\u5f53\u524d\u8bc1\u636e\u5df2\u7ecf\u7ed9\u51fa\u4e86\u540c\u9898\u8de8\u57df"
            "\u4fe1\u53f7\uff0c\u4f46\u8fd8\u4e0d\u8db3\u4ee5\u5b8c\u6210\u5b8c\u6574\u7684"
            "\u5f71\u54cd\u5206\u6790\u3002"
        )
    return (
        "Current evidence already establishes same-topic cross-domain signals, but not enough "
        "for a full impact estimate."
    )


def _build_partial_conclusion(
    *,
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    query: str,
    key_points: list[dict[str, object]],
    reason: str | None = None,
    citation_issues: tuple[str, ...] = (),
) -> str:
    use_cjk = _query_uses_cjk(query)
    evidence_by_id = {record.evidence_id: record for record in canonical_evidence}
    confirmed_parts: list[str] = []
    contextual_titles: list[str] = []
    for key_point in key_points[:2]:
        citations = key_point.get("citations", [])
        if not isinstance(citations, list) or not citations:
            continue
        first_citation = citations[0]
        if not isinstance(first_citation, dict):
            continue
        evidence_id = str(first_citation.get("evidence_id", ""))
        record = evidence_by_id.get(evidence_id)
        title = record.canonical_title if record is not None else "retained evidence"
        statement = _truncate_words(str(key_point.get("statement", "")), max_words=22)
        if statement.startswith("Related market context:"):
            if record is not None:
                contextual_titles.append(record.canonical_title)
            continue
        if statement:
            if use_cjk:
                confirmed_parts.append(f'"{title}" 显示 {statement.rstrip(".")}')
            else:
                confirmed_parts.append(f'"{title}" indicates {statement.rstrip(".")}')

    if not confirmed_parts:
        selected_matches = _select_partial_evidence_matches(
            retrieval_response,
            canonical_evidence,
            query=query,
            limit=2,
        )
        confirmed_parts = [
            (
                f'"{record.canonical_title}" 显示 {_truncate_words(slice_.text, max_words=22).rstrip(".")}'
                if use_cjk
                else f'"{record.canonical_title}" indicates {_truncate_words(slice_.text, max_words=22).rstrip(".")}'
            )
            for record, slice_ in selected_matches
        ]

    missing_summary = _partial_missing_summary(
        retrieval_response,
        canonical_evidence,
        citation_issues=citation_issues,
        reason=reason,
        use_cjk=use_cjk,
    )
    query_requirements = _partial_query_requirements(
        query,
        retrieval_response,
        canonical_evidence,
    )
    requirement_note = ""
    if query_requirements:
        requirement_summary = (
            _format_cjk_series(list(query_requirements))
            if use_cjk
            else _format_series(list(query_requirements))
        )
        requirement_note = (
            f" 这个问题还缺少：{requirement_summary}。"
            if use_cjk
            else f" What is still missing for this query: {requirement_summary}."
        )
    contextual_note = ""
    if contextual_titles:
        contextual_note = (
            f" 来自{_format_quoted_titles(contextual_titles)}的相关市场背景可以作为补充，但仍属间接证据。"
            if use_cjk
            else (
                f" Related market context from {_format_quoted_titles(contextual_titles)} is "
                "available, but it remains indirect."
            )
        )
    if not confirmed_parts:
        if use_cjk:
            return (
                f"当前来源仍然不足以完整回答这个问题。要继续补全答案，还需要{missing_summary}."
                f"{requirement_note}{contextual_note}"
            )
        return (
            "Current sources are relevant but incomplete. "
            f"A complete answer would still need {missing_summary}.{requirement_note}{contextual_note}"
        )

    confirmed_summary = "; ".join(confirmed_parts)
    has_industry = any(record.domain == "industry" for record in canonical_evidence)
    traits = derive_query_traits(query)
    if retrieval_response.route_label == "mixed":
        bridge_note = _build_mixed_partial_bridge_note(
            canonical_evidence,
            use_cjk=use_cjk,
        )
        if use_cjk:
            return (
                f"综合当前来源，可以先做一个谨慎的阶段性判断：{confirmed_summary}。"
                f"{bridge_note}"
                f"这能支持一个部分答案，但完整回答这个问题仍需要{missing_summary}."
                f"{requirement_note}{contextual_note}"
            )
        return (
            f"Taken together, current sources show these parallel signals: {confirmed_summary}. "
            f"{bridge_note} "
            f"This supports a cautious partial answer, but a complete answer would still need "
            f"{missing_summary}.{requirement_note}{contextual_note}"
        )
    if use_cjk:
        if has_industry and traits.has_trend_intent:
            return (
                f"目前可以确认的是：{confirmed_summary}。"
                f"这还只能作为方向性市场信号，完整回答这个问题仍需要{missing_summary}."
                f"{requirement_note}{contextual_note}"
            )
        return (
            f"目前可以确认的是：{confirmed_summary}。"
            f"完整回答这个问题仍需要{missing_summary}.{requirement_note}{contextual_note}"
        )
    if has_industry and traits.has_trend_intent:
        return (
            f"What can be confirmed so far is: {confirmed_summary}. "
            f"This supports only a directional market signal, and a complete answer would still need "
            f"{missing_summary}.{requirement_note}{contextual_note}"
        )
    return (
        f"What can be confirmed so far is: {confirmed_summary}. "
        f"A complete answer would still need {missing_summary}.{requirement_note}{contextual_note}"
    )


def _build_partial_response_payload(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    validated_key_points: list[dict[str, object]] | None = None,
    draft_sources: list[object] | None = None,
    citation_issues: tuple[str, ...] = (),
    reason: str | None = None,
) -> tuple[str, list[dict[str, object]], list[dict[str, str]]]:
    key_points = list(validated_key_points or [])
    matches = _select_partial_evidence_matches(
        retrieval_response,
        canonical_evidence,
        query=query,
        limit=2,
    )
    if not key_points:
        key_points = _build_key_points_from_partial_matches(matches)
    elif len(key_points) < 2:
        cited_evidence_ids = {
            str(citation.get("evidence_id"))
            for key_point in key_points
            for citation in key_point.get("citations", [])
            if isinstance(citation, dict) and citation.get("evidence_id")
        }
        for record, slice_ in matches:
            if len(key_points) >= 2 or record.evidence_id in cited_evidence_ids:
                continue
            key_points.append(
                {
                    "key_point_id": f"kp-{len(key_points) + 1}",
                    "statement": slice_.text,
                    "citations": [
                        {
                            "evidence_id": record.evidence_id,
                            "source_record_id": slice_.source_record_id,
                            "source_url": record.canonical_url,
                            "quote_text": slice_.text,
                        }
                    ],
                }
            )
            cited_evidence_ids.add(record.evidence_id)

    evidence_by_id = {record.evidence_id: record for record in canonical_evidence}
    cited_evidence_ids = [
        str(citation.get("evidence_id"))
        for key_point in key_points
        for citation in key_point.get("citations", [])
        if isinstance(citation, dict) and citation.get("evidence_id")
    ]
    sources = _dedupe_sources(
        cited_evidence_ids,
        draft_sources or [],
        evidence_by_id,
    )
    if not sources:
        for record in canonical_evidence[:2]:
            sources.append(
                {
                    "evidence_id": record.evidence_id,
                    "title": record.canonical_title,
                    "url": record.canonical_url,
                }
            )
    conclusion = _build_partial_conclusion(
        retrieval_response=retrieval_response,
        canonical_evidence=canonical_evidence,
        query=query,
        key_points=key_points,
        reason=reason,
        citation_issues=citation_issues,
    )
    return conclusion, key_points[:2], sources[:2]


def _build_retrieval_failure_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> AnswerResponse:
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=(),
    )
    return AnswerResponse(
        answer_status="retrieval_failure",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion="Retrieval failed before a grounded answer could be produced.",
        key_points=[],
        sources=[],
        uncertainty_notes=list(uncertainty_notes),
        gaps=list(retrieval_response.gaps),
    )


def _build_budget_enforced_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    reason: str,
) -> AnswerResponse:
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=(),
    )
    conclusion = "Available runtime budget was insufficient to complete grounded synthesis."
    key_points: list[dict[str, object]] = []
    sources: list[dict[str, str]] = []
    user_facing_uncertainty_notes = list(uncertainty_notes)
    if canonical_evidence:
        conclusion, key_points, sources = _build_partial_response_payload(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="remaining grounded synthesis time within the request budget",
        )
    else:
        user_facing_uncertainty_notes = [
            f"Budget enforcement: {reason}",
            *uncertainty_notes,
        ]
    return AnswerResponse(
        answer_status="insufficient_evidence",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion=conclusion,
        key_points=key_points,
        sources=sources,
        uncertainty_notes=user_facing_uncertainty_notes,
        gaps=list(retrieval_response.gaps),
    )


def _build_coverage_frontier_insufficient_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    reason: str,
) -> AnswerResponse:
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=(),
    )
    conclusion = "Available evidence was insufficient to fully support the requested answer."
    key_points: list[dict[str, object]] = []
    sources: list[dict[str, str]] = []
    if canonical_evidence:
        conclusion, key_points, sources = _build_partial_response_payload(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason=reason,
        )
    return AnswerResponse(
        answer_status="insufficient_evidence",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion=conclusion,
        key_points=key_points,
        sources=sources,
        uncertainty_notes=[f"Coverage frontier: {reason}", *uncertainty_notes],
        gaps=list(retrieval_response.gaps),
    )


def _build_relevance_gated_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
) -> AnswerResponse:
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=(),
    )
    conclusion = "Available evidence was insufficient to fully support the requested answer."
    key_points: list[dict[str, object]] = []
    sources: list[dict[str, str]] = []
    scope_note = (
        "回答范围：当前保留来源还不足以直接支撑这个问题的精确表述。"
        if _query_uses_cjk(query)
        else "Answer scope: current sources are not specific enough to ground this exact query."
    )
    if canonical_evidence:
        conclusion, key_points, sources = _build_partial_response_payload(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="query-specific evidence alignment strong enough for a complete grounded answer",
        )
    return AnswerResponse(
        answer_status="insufficient_evidence",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion=conclusion,
        key_points=key_points,
        sources=sources,
        uncertainty_notes=[
            scope_note,
            *uncertainty_notes,
        ],
        gaps=list(retrieval_response.gaps),
    )


def _build_generation_backend_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    reason: str,
) -> AnswerResponse:
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=(),
    )
    conclusion = "Available evidence was insufficient to fully support the requested answer."
    key_points: list[dict[str, object]] = []
    sources: list[dict[str, str]] = []
    if canonical_evidence:
        conclusion, key_points, sources = _build_partial_response_payload(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="a completed grounded synthesis from the generation backend",
        )
    backend_note = (
        "\u56de\u7b54\u751f\u6210\uff1a\u672c\u6b21\u5b8c\u6574\u7684\u6765\u6e90\u7efc\u5408"
        "\u672a\u80fd\u5b8c\u6210\uff0c\u56e0\u6b64\u4ee5\u4e0b\u5185\u5bb9\u4ec5\u9650\u4e8e"
        "\u5f53\u524d\u53ef\u76f4\u63a5\u652f\u6491\u7684\u8bc1\u636e\u3002"
        if _query_uses_cjk(query)
        else (
            "Answer assembly: the full source-backed synthesis did not complete, so this "
            "response is limited to directly supported evidence."
        )
    )
    del reason
    return AnswerResponse(
        answer_status="insufficient_evidence",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion=conclusion,
        key_points=key_points,
        sources=sources,
        uncertainty_notes=[
            backend_note,
            *uncertainty_notes,
        ],
        gaps=list(retrieval_response.gaps),
    )


def _build_academic_lookup_fast_path_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    matched_records: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...],
) -> AnswerResponse:
    matched_record, matched_slice, _ = matched_records[0]
    evidence_label = matched_record.canonical_title
    metadata: list[str] = []
    if matched_record.first_author:
        metadata.append(matched_record.first_author)
    if matched_record.year is not None:
        metadata.append(str(matched_record.year))
    use_cjk = _query_uses_cjk(query)
    singular_label = "paper"
    plural_label = "papers"
    if _query_contains_marker(query, _ACADEMIC_BENCHMARK_MARKERS):
        singular_label = "学术基准论文" if use_cjk else "benchmark paper"
        plural_label = "相关学术基准论文" if use_cjk else "benchmark papers"
    elif _query_contains_marker(query, _ACADEMIC_RESEARCH_MARKERS):
        singular_label = "研究" if use_cjk else "research work"
        plural_label = "相关研究" if use_cjk else "research works"
    elif use_cjk:
        singular_label = "学术论文"
        plural_label = "相关学术论文"
    metadata_suffix = f" ({', '.join(metadata)})" if metadata else ""
    if len(matched_records) > 1:
        titles = _format_quoted_titles([record.canonical_title for record, _, _ in matched_records])
        conclusion = (
            f"{plural_label}包括 {titles}."
            if use_cjk
            else f"Relevant academic {plural_label} include {titles}."
        )
    elif _query_requests_multiple_academic_items(query):
        if use_cjk:
            conclusion = (
                f'一篇直接相关的{singular_label}是 "{evidence_label}"{metadata_suffix}. '
                "更广的文献覆盖仍不完整."
            )
        else:
            conclusion = (
                f'One directly relevant academic {singular_label} is "{evidence_label}"'
                f"{metadata_suffix}. Broader literature coverage remains incomplete."
            )
    else:
        conclusion = (
            f'一篇直接相关的{singular_label}是 "{evidence_label}"{metadata_suffix}.'
            if use_cjk
            else f'A directly relevant academic {singular_label} is "{evidence_label}"{metadata_suffix}.'
        )

    draft = StructuredAnswerDraft(
        conclusion=conclusion,
        key_points=[
            KeyPoint(
                key_point_id=f"kp-{index}",
                statement=record_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=record.evidence_id,
                        source_record_id=record_slice.source_record_id,
                        source_url=record.canonical_url,
                        quote_text=record_slice.text,
                    )
                ],
            )
            for index, (record, record_slice, _) in enumerate(matched_records, start=1)
        ],
        sources=[
            SourceReference(
                evidence_id=record.evidence_id,
                title=record.canonical_title,
                url=record.canonical_url,
            )
            for record, _, _ in matched_records
        ],
        uncertainty_notes=[],
        gaps=[],
    )
    return _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
        local_fast_path=True,
        uncertainty_focus_evidence_ids=tuple(
            record.evidence_id for record, _, _ in matched_records
        ),
    )


def _build_policy_lookup_fast_path_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    matched_record: CanonicalEvidence,
    supporting_matches: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...] = (),
) -> AnswerResponse:
    matched_slice = matched_record.retained_slices[0]
    use_cjk = _query_uses_cjk(query)
    metadata: list[str] = []
    if matched_record.authority:
        metadata.append(
            f"发布机构 {matched_record.authority}" if use_cjk else matched_record.authority
        )
    if matched_record.version is not None:
        metadata.append(
            f"版本 {matched_record.version}" if use_cjk else f"version {matched_record.version}"
        )
    if matched_record.effective_date is not None:
        metadata.append(
            f"自 {matched_record.effective_date} 起生效"
            if use_cjk
            else f"effective {matched_record.effective_date}"
        )
    elif matched_record.publication_date is not None:
        metadata.append(
            f"发布时间 {matched_record.publication_date}"
            if use_cjk
            else f"published {matched_record.publication_date}"
        )

    conclusion_prefix = "最相关的官方政策是" if use_cjk else "The most relevant official policy is"
    if _query_contains_marker(query, _POLICY_EXEMPTION_MARKERS):
        conclusion_prefix = (
            "最相关的官方豁免指引是" if use_cjk else "The most relevant official exemption guidance is"
        )
    elif _query_contains_marker(query, _POLICY_CHANGE_MARKERS):
        conclusion_prefix = (
            "最相关的官方政策变化文件是" if use_cjk else "The most relevant official policy change is"
        )

    conclusion = f'{conclusion_prefix} "{matched_record.canonical_title}".'
    if metadata:
        conclusion = (
            f'{conclusion_prefix} "{matched_record.canonical_title}"'
            f" ({'；'.join(metadata) if use_cjk else '; '.join(metadata)})."
        )
    if supporting_matches:
        conclusion = (
            (
                f"{conclusion} 补充官方依据还包括 "
                f"{_format_quoted_titles([record.canonical_title for record, _, _ in supporting_matches])}."
            )
            if use_cjk
            else (
                f"{conclusion} Supporting official evidence also includes "
                f"{_format_quoted_titles([record.canonical_title for record, _, _ in supporting_matches])}."
            )
        )

    draft = StructuredAnswerDraft(
        conclusion=conclusion,
        key_points=[
            KeyPoint(
                key_point_id="kp-1",
                statement=matched_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=matched_record.evidence_id,
                        source_record_id=matched_slice.source_record_id,
                        source_url=matched_record.canonical_url,
                        quote_text=matched_slice.text,
                    )
                ],
            )
        ]
        + [
            KeyPoint(
                key_point_id=f"kp-{index}",
                statement=record_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=record.evidence_id,
                        source_record_id=record_slice.source_record_id,
                        source_url=record.canonical_url,
                        quote_text=record_slice.text,
                    )
                ],
            )
            for index, (record, record_slice, _) in enumerate(supporting_matches, start=2)
        ],
        sources=[
            SourceReference(
                evidence_id=matched_record.evidence_id,
                title=matched_record.canonical_title,
                url=matched_record.canonical_url,
            )
        ]
        + [
            SourceReference(
                evidence_id=record.evidence_id,
                title=record.canonical_title,
                url=record.canonical_url,
            )
            for record, _, _ in supporting_matches
        ],
        uncertainty_notes=[],
        gaps=[],
    )
    return _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
        local_fast_path=True,
        uncertainty_focus_evidence_ids=(matched_record.evidence_id,),
    )


def _build_industry_lookup_fast_path_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    matched_record: CanonicalEvidence,
    matched_slice: EvidenceSlice,
    supporting_matches: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...] = (),
) -> AnswerResponse:
    direct_supporting_matches, contextual_supporting_match = (
        _partition_industry_supporting_matches(
            query,
            matched_record,
            supporting_matches,
        )
    )
    use_cjk = _query_uses_cjk(query)
    single_source_outlook = (
        not direct_supporting_matches
        and contextual_supporting_match is None
        and derive_query_traits(query).has_trend_intent
    )
    if single_source_outlook:
        if use_cjk:
            conclusion = (
                f'目前可以确认的是，"{matched_record.canonical_title}" 是这类 2026 年行业展望的直接来源之一，'
                "但当前片段还没有给出实际预测数值、细分拆分或第二个交叉来源。"
            )
        else:
            conclusion = (
                f'What can be confirmed so far is that "{matched_record.canonical_title}" '
                "is a direct source on this 2026 outlook, but the retained snippet does not "
                "expose the actual forecast figures, segment split, or a second corroborating source."
            )
    else:
        conclusion = (
            f'当前最直接的行业来源是 "{matched_record.canonical_title}"。'
            if use_cjk
            else f'The strongest direct industry source is "{matched_record.canonical_title}".'
        )
    if direct_supporting_matches:
        supporting_titles = _format_quoted_titles(
            [record.canonical_title for record, _, _ in direct_supporting_matches]
        )
        conclusion = (
            f"{conclusion} 补充行业佐证还包括 {supporting_titles}。"
            if use_cjk
            else f"{conclusion} Additional industry evidence also includes {supporting_titles}."
        )
    elif contextual_supporting_match is not None:
        contextual_record, _, _ = contextual_supporting_match
        conclusion = (
            f'{conclusion} 相关市场背景还包括 "{contextual_record.canonical_title}"，但它仍不是直接回答这个问题的证据。'
            if use_cjk
            else (
                f'{conclusion} Related market context also includes '
                f'"{contextual_record.canonical_title}", but it is not direct evidence '
                "for the requested answer."
            )
        )

    draft = StructuredAnswerDraft(
        conclusion=conclusion,
        key_points=[
            KeyPoint(
                key_point_id="kp-1",
                statement=matched_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=matched_record.evidence_id,
                        source_record_id=matched_slice.source_record_id,
                        source_url=matched_record.canonical_url,
                        quote_text=matched_slice.text,
                    )
                ],
            )
        ]
        + [
            KeyPoint(
                key_point_id=f"kp-{index}",
                statement=record_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=record.evidence_id,
                        source_record_id=record_slice.source_record_id,
                        source_url=record.canonical_url,
                        quote_text=record_slice.text,
                    )
                ],
            )
            for index, (record, record_slice, _) in enumerate(direct_supporting_matches, start=2)
        ],
        sources=[
            SourceReference(
                evidence_id=matched_record.evidence_id,
                title=matched_record.canonical_title,
                url=matched_record.canonical_url,
            )
        ]
        + [
            SourceReference(
                evidence_id=record.evidence_id,
                title=record.canonical_title,
                url=record.canonical_url,
            )
            for record, _, _ in direct_supporting_matches
        ]
        + (
            [
                SourceReference(
                    evidence_id=contextual_supporting_match[0].evidence_id,
                    title=contextual_supporting_match[0].canonical_title,
                    url=contextual_supporting_match[0].canonical_url,
                )
            ]
            if contextual_supporting_match is not None
            else []
        ),
        uncertainty_notes=[],
        gaps=[],
    )
    if contextual_supporting_match is not None:
        contextual_record, contextual_slice, _ = contextual_supporting_match
        draft.key_points.append(
            KeyPoint(
                key_point_id=f"kp-{len(draft.key_points) + 1}",
                statement=f"Related market context: {contextual_slice.text}",
                citations=[
                    ClaimCitation(
                        evidence_id=contextual_record.evidence_id,
                        source_record_id=contextual_slice.source_record_id,
                        source_url=contextual_record.canonical_url,
                        quote_text=contextual_slice.text,
                    )
                ],
            )
        )
    return _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
        query=query,
        local_fast_path=True,
        answer_status_override=(
            "insufficient_evidence"
            if retrieval_response.status == "partial"
            else None
        ),
        uncertainty_focus_evidence_ids=(matched_record.evidence_id,),
    )


def _build_mixed_cross_domain_fast_path_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    matched_primary_record: CanonicalEvidence,
    matched_primary_slice: EvidenceSlice,
    matched_supplemental_record: CanonicalEvidence,
    matched_supplemental_slice: EvidenceSlice,
) -> AnswerResponse:
    use_cjk = _query_uses_cjk(query)
    primary_statement = matched_primary_slice.text.rstrip(".")
    supplemental_statement = matched_supplemental_slice.text.rstrip(".")
    if use_cjk:
        conclusion = (
            f'现有来源显示的影响线索是："{matched_primary_record.canonical_title}" 表明 {primary_statement}；'
            f'"{matched_supplemental_record.canonical_title}" 表明 {supplemental_statement}。'
        )
    else:
        conclusion = (
            f'Current sources indicate an impact pattern: "{matched_primary_record.canonical_title}" shows '
            f"{primary_statement}, and "
            f'"{matched_supplemental_record.canonical_title}" shows {supplemental_statement}.'
        )
    if {matched_primary_record.domain, matched_supplemental_record.domain} == {
        "policy",
        "academic",
    }:
        policy_text = normalize_query_text(
            " ".join(
                (
                    matched_primary_record.canonical_title,
                    matched_primary_slice.text,
                    matched_primary_record.version or "",
                )
            )
        )
        licensing_constrained = any(
            marker in policy_text
            for marker in ("license", "licence", "licensing", "许可", "许可证")
        )
        if use_cjk:
            constraint_label = "许可要求" if licensing_constrained else "政策要求"
            conclusion = (
                f"{conclusion} 这表明{constraint_label}可能改变研究条件，但现有来源并未量化这种影响。"
            )
        else:
            constraint_label = (
                "licensing requirements"
                if licensing_constrained
                else "policy requirements"
            )
            conclusion = (
                f"{conclusion} Together, these sources suggest {constraint_label} can "
                "reshape research conditions, but the cited sources do not quantify "
                "the size of that effect."
            )

    draft = StructuredAnswerDraft(
        conclusion=conclusion,
        key_points=[
            KeyPoint(
                key_point_id="kp-1",
                statement=matched_primary_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=matched_primary_record.evidence_id,
                        source_record_id=matched_primary_slice.source_record_id,
                        source_url=matched_primary_record.canonical_url,
                        quote_text=matched_primary_slice.text,
                    )
                ],
            ),
            KeyPoint(
                key_point_id="kp-2",
                statement=matched_supplemental_slice.text,
                citations=[
                    ClaimCitation(
                        evidence_id=matched_supplemental_record.evidence_id,
                        source_record_id=matched_supplemental_slice.source_record_id,
                        source_url=matched_supplemental_record.canonical_url,
                        quote_text=matched_supplemental_slice.text,
                    )
                ],
            ),
        ],
        sources=[
            SourceReference(
                evidence_id=matched_primary_record.evidence_id,
                title=matched_primary_record.canonical_title,
                url=matched_primary_record.canonical_url,
            ),
            SourceReference(
                evidence_id=matched_supplemental_record.evidence_id,
                title=matched_supplemental_record.canonical_title,
                url=matched_supplemental_record.canonical_url,
            ),
        ],
        uncertainty_notes=[],
        gaps=[],
    )
    return _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
        local_fast_path=True,
        uncertainty_focus_evidence_ids=(
            matched_primary_record.evidence_id,
            matched_supplemental_record.evidence_id,
        ),
    )


def _build_local_answer_candidate(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    *,
    query: str,
    require_clean_runtime: bool,
) -> AnswerResponse | None:
    partial_industry_lookup_allowed = (
        retrieval_response.status == "partial"
        and retrieval_response.route_label != "mixed"
        and retrieval_response.primary_route == "industry"
        and _is_industry_lookup_query(query)
    )
    partial_mixed_cross_domain_allowed = (
        retrieval_response.status == "partial"
        and retrieval_response.route_label == "mixed"
        and retrieval_response.supplemental_route is not None
        and _is_cross_domain_effect_query(query)
    )

    if retrieval_response.status not in {"success", "partial"}:
        return None
    if retrieval_response.status == "partial" and not (
        partial_industry_lookup_allowed or partial_mixed_cross_domain_allowed
    ):
        return None

    if require_clean_runtime and (
        retrieval_response.evidence_pruned
        or (
            retrieval_response.gaps
            and not (
                partial_industry_lookup_allowed
                or partial_mixed_cross_domain_allowed
            )
        )
    ):
        return None

    query_terms = _content_terms(query)
    best_slice_overlap, best_record, best_slice = _best_slice_overlap(
        query_terms,
        canonical_evidence,
    )
    matched_policy_record = _best_policy_lookup_record(query, canonical_evidence)
    policy_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="policy",
        route_role="primary",
        limit=2,
    )
    supporting_policy_matches = ()
    if matched_policy_record is not None:
        supporting_policy_matches = tuple(
            match
            for match in policy_matches
            if match[0].evidence_id != matched_policy_record.evidence_id
        )
    primary_route_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain=retrieval_response.primary_route,
        route_role="primary",
        limit=2,
    )
    primary_route_overlap = 0
    primary_route_record: CanonicalEvidence | None = None
    primary_route_slice: EvidenceSlice | None = None
    if primary_route_matches:
        primary_route_record, primary_route_slice, primary_route_overlap = primary_route_matches[0]

    supplemental_route_matches: tuple[tuple[CanonicalEvidence, EvidenceSlice, int], ...] = ()
    supplemental_route_overlap = 0
    supplemental_route_record: CanonicalEvidence | None = None
    supplemental_route_slice: EvidenceSlice | None = None
    if retrieval_response.supplemental_route is not None:
        supplemental_route_matches = _top_route_matches(
            query,
            canonical_evidence,
            domain=retrieval_response.supplemental_route,
            route_role="supplemental",
            limit=1,
        )
        if supplemental_route_matches:
            (
                supplemental_route_record,
                supplemental_route_slice,
                supplemental_route_overlap,
            ) = supplemental_route_matches[0]

    cross_domain_dual_route_allowed = (
        retrieval_response.supplemental_route is not None
        and _is_cross_domain_effect_query(query)
        and (
            retrieval_response.route_label == "mixed"
            or retrieval_response.primary_route == "policy"
        )
    )

    if (
        cross_domain_dual_route_allowed
        and primary_route_record is not None
        and primary_route_slice is not None
        and supplemental_route_record is not None
        and supplemental_route_slice is not None
        and primary_route_overlap >= min(2, len(query_terms))
        and supplemental_route_overlap >= min(2, len(query_terms))
        and (
            not require_clean_runtime
            or not retrieval_response.gaps
            or partial_mixed_cross_domain_allowed
        )
    ):
        return _build_mixed_cross_domain_fast_path_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            matched_primary_record=primary_route_record,
            matched_primary_slice=primary_route_slice,
            matched_supplemental_record=supplemental_route_record,
            matched_supplemental_slice=supplemental_route_slice,
        )

    if (
        retrieval_response.route_label != "mixed"
        and retrieval_response.primary_route == "policy"
        and _is_policy_lookup_query(query)
        and matched_policy_record is not None
        and (
            not require_clean_runtime
            or (
                not retrieval_response.gaps
                and (
                    not retrieval_response.evidence_clipped
                    or bool(supporting_policy_matches)
                )
            )
        )
    ):
        return _build_policy_lookup_fast_path_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            matched_record=matched_policy_record,
            supporting_matches=supporting_policy_matches,
        )

    industry_matches = _top_route_matches(
        query,
        canonical_evidence,
        domain="industry",
        route_role="primary",
        limit=2,
    )
    supporting_industry_matches = industry_matches[1:] if len(industry_matches) > 1 else ()
    if (
        retrieval_response.route_label != "mixed"
        and retrieval_response.primary_route == "industry"
        and _is_industry_lookup_query(query)
        and industry_matches
        and industry_matches[0][0] is not None
        and industry_matches[0][1] is not None
        and industry_matches[0][2] >= min(2, len(query_terms))
        and (
            not require_clean_runtime
            or not retrieval_response.gaps
            or partial_industry_lookup_allowed
        )
    ):
        return _build_industry_lookup_fast_path_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            matched_record=industry_matches[0][0],
            matched_slice=industry_matches[0][1],
            supporting_matches=supporting_industry_matches,
        )

    return None


def _response_text(response: AnswerResponse) -> str:
    return "\n".join(
        [
            response.conclusion,
            *[key_point.statement for key_point in response.key_points],
            *[source.title for source in response.sources],
        ]
    )


def _local_candidate_should_override(
    *,
    query: str,
    generated_response: AnswerResponse,
    local_candidate: AnswerResponse | None,
) -> bool:
    if local_candidate is None or local_candidate.answer_status != "grounded_success":
        return False
    if generated_response.answer_status != "grounded_success":
        return True

    generated_text = _response_text(generated_response)
    local_text = _response_text(local_candidate)
    normalized_generated = normalize_query_text(generated_text)
    normalized_local = normalize_query_text(local_text)
    generated_dates = set(_DATE_LITERAL_RE.findall(generated_text))
    local_dates = set(_DATE_LITERAL_RE.findall(local_text))
    generated_years = set(_YEAR_LITERAL_RE.findall(generated_text))
    local_years = set(_YEAR_LITERAL_RE.findall(local_text))
    local_versions = {normalize_query_text(match) for match in _VERSION_LITERAL_RE.findall(local_text)}
    traits = derive_query_traits(query)

    if len(generated_response.sources) < len(local_candidate.sources):
        return True
    if len(generated_response.key_points) < len(local_candidate.key_points):
        return True

    if traits.has_effective_date_intent and local_dates and not local_dates <= generated_dates:
        return True
    if traits.has_year and local_years and not local_years <= generated_years:
        return True
    if (traits.has_version_intent or traits.is_policy_change) and local_versions:
        if any(version_phrase not in normalized_generated for version_phrase in local_versions):
            return True
    if any(
        normalize_query_text(source.title) not in normalized_generated
        for source in local_candidate.sources
    ):
        return True
    if len(normalized_generated) < len(normalized_local) // 2:
        return True

    return False


def _build_answer_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    draft,
    *,
    query: str | None = None,
    local_fast_path: bool = False,
    answer_status_override: str | None = None,
    uncertainty_focus_evidence_ids: tuple[str, ...] = (),
) -> AnswerResponse:
    citation_result = validate_answer_citations(draft, canonical_evidence)
    computed_answer_status = determine_answer_status(
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        canonical_evidence_count=len(canonical_evidence),
        grounded_key_point_count=citation_result.grounded_key_point_count,
        total_key_point_count=citation_result.total_key_point_count,
    )
    answer_status = answer_status_override or computed_answer_status
    validated_key_points = [
        {
            "key_point_id": key_point.key_point_id,
            "statement": key_point.statement,
            "citations": [
                {
                    "evidence_id": citation.evidence_id,
                    "source_record_id": citation.source_record_id,
                    "source_url": citation.source_url,
                    "quote_text": citation.quote_text,
                }
                for citation in key_point.citations
            ],
        }
        for key_point in citation_result.validated_key_points
    ]
    cited_evidence_ids = [
        citation["evidence_id"]
        for key_point in validated_key_points
        for citation in key_point["citations"]
    ]
    evidence_by_id = {record.evidence_id: record for record in canonical_evidence}
    sources = _dedupe_sources(cited_evidence_ids, draft.sources, evidence_by_id)
    strong_local_grounding = (
        local_fast_path
        and answer_status == "grounded_success"
        and (
            retrieval_response.status == "success"
            or (
                retrieval_response.primary_route == "academic"
                and retrieval_response.status == "partial"
                and retrieval_response.failure_reason == "no_hits"
                and not retrieval_response.gaps
            )
        )
        and not retrieval_response.gaps
        and not citation_result.issues
        and len(sources) >= 2
    )
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=citation_result.issues,
        cited_evidence_ids=tuple(cited_evidence_ids),
        focus_evidence_ids=uncertainty_focus_evidence_ids,
        strong_local_grounding=strong_local_grounding,
    )

    conclusion = draft.conclusion
    if (
        answer_status == "insufficient_evidence"
        and query is not None
        and canonical_evidence
    ):
        conclusion, validated_key_points, sources = _build_partial_response_payload(
            retrieval_response,
            canonical_evidence,
            query=query,
            validated_key_points=validated_key_points,
            draft_sources=draft.sources,
            citation_issues=citation_result.issues,
        )
    elif answer_status == "insufficient_evidence":
        conclusion = "Available evidence was insufficient to fully support the requested answer."

    return AnswerResponse(
        answer_status=answer_status,
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion=conclusion,
        key_points=validated_key_points,
        sources=sources,
        uncertainty_notes=list(uncertainty_notes),
        gaps=list(retrieval_response.gaps),
    )


def _build_runtime_trace(
    *,
    request_id: str,
    response: AnswerResponse,
    retrieval_elapsed_seconds: float,
    synthesis_elapsed_seconds: float,
    evidence_token_estimate: int,
    answer_token_estimate: int | None,
    runtime_budget: RuntimeBudget,
    budget_exhausted_phase: str | None,
    provider_prompt_tokens: int | None = None,
    provider_completion_tokens: int | None = None,
    provider_total_tokens: int | None = None,
    retrieval_trace: tuple[dict[str, object], ...] = (),
) -> RuntimeTrace:
    elapsed_seconds = retrieval_elapsed_seconds + synthesis_elapsed_seconds
    latency_budget_ok = (
        retrieval_elapsed_seconds <= runtime_budget.retrieval_deadline_seconds
        and elapsed_seconds <= runtime_budget.request_deadline_seconds
        and budget_exhausted_phase != "synthesis"
    )
    token_budget_ok = (
        evidence_token_estimate <= runtime_budget.evidence_token_budget
        and (
            answer_token_estimate is None
            or answer_token_estimate <= runtime_budget.answer_token_budget
        )
    )
    return RuntimeTrace(
        request_id=request_id,
        route_label=response.route_label,
        answer_status=response.answer_status,
        retrieval_status=response.retrieval_status,
        elapsed_ms=int(round(elapsed_seconds * 1000)),
        retrieval_elapsed_ms=int(round(retrieval_elapsed_seconds * 1000)),
        synthesis_elapsed_ms=int(round(synthesis_elapsed_seconds * 1000)),
        evidence_token_estimate=evidence_token_estimate,
        answer_token_estimate=answer_token_estimate,
        latency_budget_ok=latency_budget_ok,
        token_budget_ok=token_budget_ok,
        failure_reason=response.failure_reason,
        budget_exhausted_phase=budget_exhausted_phase,
        provider_prompt_tokens=provider_prompt_tokens,
        provider_completion_tokens=provider_completion_tokens,
        provider_total_tokens=provider_total_tokens,
        retrieval_trace=retrieval_trace,
    )


def _extract_provider_usage(
    model_client: ModelClient,
) -> tuple[int | None, int | None, int | None]:
    raw_usage = getattr(model_client, "last_usage", None)
    if not isinstance(raw_usage, Mapping):
        return None, None, None

    def _read_usage(field_name: str) -> int | None:
        value = raw_usage.get(field_name)
        return value if isinstance(value, int) and value >= 0 else None

    return (
        _read_usage("prompt_tokens"),
        _read_usage("completion_tokens"),
        _read_usage("total_tokens"),
    )


def _cached_entry_within_budget(
    entry: CachedAnswerEntry,
    *,
    runtime_budget: RuntimeBudget,
) -> bool:
    if entry.evidence_token_estimate > runtime_budget.evidence_token_budget:
        return False
    if (
        entry.answer_token_estimate is not None
        and entry.answer_token_estimate > runtime_budget.answer_token_budget
    ):
        return False
    return True


def _should_cache_response(response: AnswerResponse) -> bool:
    return (
        response.answer_status == "grounded_success"
        and response.retrieval_status == "success"
        and response.failure_reason is None
        and not response.gaps
        and not response.uncertainty_notes
    )


def _maybe_cache_response(
    *,
    query: str,
    plan,
    response: AnswerResponse,
    evidence_token_estimate: int,
    answer_token_estimate: int | None,
    retrieval_trace: tuple[dict[str, object], ...] = (),
) -> None:
    if not _should_cache_response(response):
        return
    ANSWER_CACHE.put(
        query=query,
        plan=plan,
        response=response,
        evidence_token_estimate=evidence_token_estimate,
        answer_token_estimate=answer_token_estimate,
        retrieval_trace=retrieval_trace,
    )


def _build_answer_artifacts(
    *,
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
) -> dict[str, object]:
    return {
        "retrieve": {
            "status": retrieval_response.status,
            "failure_reason": retrieval_response.failure_reason,
            "gaps": list(retrieval_response.gaps),
            "canonical_evidence": [
                item.model_dump()
                for item in _shape_canonical_evidence(canonical_evidence)
            ],
            "evidence_clipped": retrieval_response.evidence_clipped,
            "evidence_pruned": retrieval_response.evidence_pruned,
        }
    }


def _build_answer_execution_result(
    *,
    request_id: str,
    response: AnswerResponse,
    retrieval_response: RetrieveResponse | None,
    canonical_evidence: tuple[CanonicalEvidence, ...] | None,
    retrieval_elapsed_seconds: float,
    synthesis_elapsed_seconds: float,
    evidence_token_estimate: int,
    answer_token_estimate: int | None,
    runtime_budget: RuntimeBudget,
    budget_exhausted_phase: str | None,
    retrieval_trace: tuple[dict[str, object], ...],
    provider_prompt_tokens: int | None = None,
    provider_completion_tokens: int | None = None,
    provider_total_tokens: int | None = None,
) -> AnswerExecutionResult:
    artifacts: dict[str, object] | None = None
    if retrieval_response is not None and canonical_evidence is not None:
        artifacts = _build_answer_artifacts(
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
        )
    return AnswerExecutionResult(
        response=response,
        runtime_trace=_build_runtime_trace(
            request_id=request_id,
            response=response,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=synthesis_elapsed_seconds,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=runtime_budget,
            budget_exhausted_phase=budget_exhausted_phase,
            provider_prompt_tokens=provider_prompt_tokens,
            provider_completion_tokens=provider_completion_tokens,
            provider_total_tokens=provider_total_tokens,
            retrieval_trace=retrieval_trace,
        ),
        artifacts=artifacts,
    )


async def execute_answer_pipeline_with_trace(
    plan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    model_client: ModelClient,
    runtime_budget: RuntimeBudget | None = None,
) -> AnswerExecutionResult:
    """Compose retrieval, generation, citation validation, and runtime tracing."""
    budget = runtime_budget or RuntimeBudget.from_env()
    request_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    retrieval_deadline_seconds = budget.retrieval_deadline_seconds
    if (
        plan.route_label == "industry"
        and plan.primary_route == "industry"
        and _is_industry_lookup_query(query)
    ):
        retrieval_deadline_seconds = max(
            retrieval_deadline_seconds,
            plan.overall_deadline_seconds,
        )
    budget = replace(
        budget,
        retrieval_deadline_seconds=retrieval_deadline_seconds,
    )
    retrieval_plan = replace(
        plan,
        overall_deadline_seconds=min(
            plan.overall_deadline_seconds,
            retrieval_deadline_seconds,
        ),
    )
    cached_entry = ANSWER_CACHE.get(query=query, plan=retrieval_plan)
    if cached_entry is not None and _cached_entry_within_budget(
        cached_entry,
        runtime_budget=budget,
    ):
        response = cached_entry.response
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=None,
            canonical_evidence=None,
            retrieval_elapsed_seconds=0.0,
            synthesis_elapsed_seconds=0.0,
            evidence_token_estimate=cached_entry.evidence_token_estimate,
            answer_token_estimate=cached_entry.answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=None,
            retrieval_trace=cached_entry.retrieval_trace,
        )
    retrieval_response = await execute_retrieval_pipeline(
        plan=retrieval_plan,
        query=query,
        adapter_registry=adapter_registry,
    )
    retrieval_trace = consume_last_retrieval_trace()
    retrieval_elapsed_seconds = time.perf_counter() - started_at
    canonical_evidence = tuple(
        _rehydrate_canonical_evidence(item)
        for item in retrieval_response.canonical_evidence
    )
    evidence_token_estimate = _estimate_evidence_tokens(canonical_evidence)
    budget_exhausted_phase: str | None = None
    provider_prompt_tokens: int | None = None
    provider_completion_tokens: int | None = None
    provider_total_tokens: int | None = None
    local_fast_path_response: AnswerResponse | None = None

    if retrieval_response.status == "failure_gaps" and not canonical_evidence:
        response = _build_retrieval_failure_response(
            retrieval_response,
            canonical_evidence,
        )
        answer_token_estimate = _estimate_response_tokens(response)
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=0.0,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=None,
            retrieval_trace=retrieval_trace,
        )

    if (
        retrieval_response.primary_route == "academic"
        and _academic_fast_path_runtime_ok(retrieval_response)
        and canonical_evidence
        and _is_academic_lookup_query(query)
    ):
        academic_primary_matches = _top_route_matches(
            query,
            canonical_evidence,
            domain="academic",
            route_role="primary",
            limit=_academic_lookup_candidate_limit(query),
        )
        academic_matches = _select_academic_lookup_matches(
            query,
            academic_primary_matches,
        )
        if academic_matches and _academic_fast_path_match_allowed(
            query,
            record=academic_matches[0][0],
            matched_slice=academic_matches[0][1],
            slice_overlap=academic_matches[0][2],
        ):
            local_fast_path_response = _build_academic_lookup_fast_path_response(
                retrieval_response,
                canonical_evidence,
                query=query,
                matched_records=academic_matches,
            )
            if not _should_attempt_same_route_enrichment(
                retrieval_response,
                canonical_evidence,
                query=query,
                local_candidate=local_fast_path_response,
            ):
                response = local_fast_path_response
                answer_token_estimate = _estimate_response_tokens(response)
                _maybe_cache_response(
                    query=query,
                    plan=retrieval_plan,
                    response=response,
                    evidence_token_estimate=evidence_token_estimate,
                    answer_token_estimate=answer_token_estimate,
                    retrieval_trace=retrieval_trace,
                )
                return _build_answer_execution_result(
                    request_id=request_id,
                    response=response,
                    retrieval_response=retrieval_response,
                    canonical_evidence=canonical_evidence,
                    retrieval_elapsed_seconds=retrieval_elapsed_seconds,
                    synthesis_elapsed_seconds=0.0,
                    evidence_token_estimate=evidence_token_estimate,
                    answer_token_estimate=answer_token_estimate,
                    runtime_budget=budget,
                    budget_exhausted_phase=None,
                    retrieval_trace=retrieval_trace,
                )

    if local_fast_path_response is None:
        local_fast_path_response = _build_local_answer_candidate(
            retrieval_response,
            canonical_evidence,
            query=query,
            require_clean_runtime=True,
        )

    if local_fast_path_response is not None:
        (
            retrieval_response,
            canonical_evidence,
            retrieval_trace,
            same_route_enrichment_elapsed_seconds,
            enriched_local_response,
        ) = await _maybe_apply_same_route_enrichment(
            query=query,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            local_fast_path_response=local_fast_path_response,
            adapter_registry=adapter_registry,
            runtime_budget=budget,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            retrieval_trace=retrieval_trace,
        )
        if same_route_enrichment_elapsed_seconds > 0:
            retrieval_elapsed_seconds += same_route_enrichment_elapsed_seconds
            evidence_token_estimate = _estimate_evidence_tokens(canonical_evidence)
        if enriched_local_response is not None:
            local_fast_path_response = enriched_local_response

    if local_fast_path_response is None:
        (
            retrieval_response,
            canonical_evidence,
            retrieval_trace,
            supplemental_probe_elapsed_seconds,
            coverage_frontier_response,
        ) = await _maybe_apply_coverage_frontier_policy(
            query=query,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            adapter_registry=adapter_registry,
            runtime_budget=budget,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            retrieval_trace=retrieval_trace,
        )
        if supplemental_probe_elapsed_seconds > 0:
            retrieval_elapsed_seconds += supplemental_probe_elapsed_seconds
            evidence_token_estimate = _estimate_evidence_tokens(canonical_evidence)
        if coverage_frontier_response is not None:
            response = coverage_frontier_response
            answer_token_estimate = _estimate_response_tokens(response)
            return _build_answer_execution_result(
                request_id=request_id,
                response=response,
                retrieval_response=retrieval_response,
                canonical_evidence=canonical_evidence,
                retrieval_elapsed_seconds=retrieval_elapsed_seconds,
                synthesis_elapsed_seconds=0.0,
                evidence_token_estimate=evidence_token_estimate,
                answer_token_estimate=answer_token_estimate,
                runtime_budget=budget,
                budget_exhausted_phase=None,
                retrieval_trace=retrieval_trace,
            )
        local_fast_path_response = _build_local_answer_candidate(
            retrieval_response,
            canonical_evidence,
            query=query,
            require_clean_runtime=True,
        )
    if local_fast_path_response is not None:
        response = local_fast_path_response
        answer_token_estimate = _estimate_response_tokens(response)
        _maybe_cache_response(
            query=query,
            plan=retrieval_plan,
            response=response,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            retrieval_trace=retrieval_trace,
        )
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=0.0,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=None,
            retrieval_trace=retrieval_trace,
        )

    local_guardrail_candidate = _build_local_answer_candidate(
        retrieval_response,
        canonical_evidence,
        query=query,
        require_clean_runtime=False,
    )

    if canonical_evidence and not _has_query_evidence_overlap(
        query,
        canonical_evidence,
        primary_route=retrieval_response.primary_route,
    ):
        response = _build_relevance_gated_response(
            retrieval_response,
            canonical_evidence,
            query=query,
        )
        answer_token_estimate = _estimate_response_tokens(response)
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=0.0,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=None,
            retrieval_trace=retrieval_trace,
        )

    remaining_synthesis_seconds = budget.remaining_synthesis_seconds(
        retrieval_elapsed_seconds=retrieval_elapsed_seconds,
    )
    if remaining_synthesis_seconds <= 0:
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="no synthesis time remained within the request budget.",
        )
        answer_token_estimate = _estimate_response_tokens(response)
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=0.0,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase="synthesis",
            retrieval_trace=retrieval_trace,
        )

    prompt = build_grounded_answer_prompt(
        query=query,
        canonical_evidence=canonical_evidence,
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        retrieval_gaps=tuple(retrieval_response.gaps),
    )
    synthesis_started_at = time.perf_counter()
    try:
        draft = generate_answer_draft(
            prompt,
            model_client=model_client,
            timeout_seconds=remaining_synthesis_seconds,
        )
        (
            provider_prompt_tokens,
            provider_completion_tokens,
            provider_total_tokens,
        ) = _extract_provider_usage(model_client)
    except TimeoutError:
        (
            provider_prompt_tokens,
            provider_completion_tokens,
            provider_total_tokens,
        ) = _extract_provider_usage(model_client)
        budget_exhausted_phase = "synthesis"
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="grounded synthesis exceeded the remaining request budget.",
        )
        synthesis_elapsed_seconds = time.perf_counter() - synthesis_started_at
        answer_token_estimate = _estimate_response_tokens(response)
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=synthesis_elapsed_seconds,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=budget_exhausted_phase,
            provider_prompt_tokens=provider_prompt_tokens,
            provider_completion_tokens=provider_completion_tokens,
            provider_total_tokens=provider_total_tokens,
            retrieval_trace=retrieval_trace,
        )
    except ModelBackendError as exc:
        (
            provider_prompt_tokens,
            provider_completion_tokens,
            provider_total_tokens,
        ) = _extract_provider_usage(model_client)
        response = _build_generation_backend_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason=str(exc),
        )
        synthesis_elapsed_seconds = time.perf_counter() - synthesis_started_at
        answer_token_estimate = _estimate_response_tokens(response)
        return _build_answer_execution_result(
            request_id=request_id,
            response=response,
            retrieval_response=retrieval_response,
            canonical_evidence=canonical_evidence,
            retrieval_elapsed_seconds=retrieval_elapsed_seconds,
            synthesis_elapsed_seconds=synthesis_elapsed_seconds,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            runtime_budget=budget,
            budget_exhausted_phase=None,
            provider_prompt_tokens=provider_prompt_tokens,
            provider_completion_tokens=provider_completion_tokens,
            provider_total_tokens=provider_total_tokens,
            retrieval_trace=retrieval_trace,
        )

    response = _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
        query=query,
    )
    if _local_candidate_should_override(
        query=query,
        generated_response=response,
        local_candidate=local_guardrail_candidate,
    ):
        response = local_guardrail_candidate
    synthesis_elapsed_seconds = time.perf_counter() - synthesis_started_at
    answer_token_estimate = _estimate_response_tokens(response)

    if answer_token_estimate > budget.answer_token_budget:
        budget_exhausted_phase = "answer_tokens"
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            query=query,
            reason="grounded output would exceed the answer token budget.",
        )
    else:
        _maybe_cache_response(
            query=query,
            plan=retrieval_plan,
            response=response,
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            retrieval_trace=retrieval_trace,
        )

    return _build_answer_execution_result(
        request_id=request_id,
        response=response,
        retrieval_response=retrieval_response,
        canonical_evidence=canonical_evidence,
        retrieval_elapsed_seconds=retrieval_elapsed_seconds,
        synthesis_elapsed_seconds=synthesis_elapsed_seconds,
        evidence_token_estimate=evidence_token_estimate,
        answer_token_estimate=answer_token_estimate,
        runtime_budget=budget,
        budget_exhausted_phase=budget_exhausted_phase,
        provider_prompt_tokens=provider_prompt_tokens,
        provider_completion_tokens=provider_completion_tokens,
        provider_total_tokens=provider_total_tokens,
        retrieval_trace=retrieval_trace,
    )


async def execute_answer_pipeline(
    plan,
    query: str,
    adapter_registry: Mapping[str, Adapter],
    model_client: ModelClient,
) -> AnswerResponse:
    """Backward-compatible wrapper returning the public response only."""
    result = await execute_answer_pipeline_with_trace(
        plan=plan,
        query=query,
        adapter_registry=adapter_registry,
        model_client=model_client,
    )
    return result.response
