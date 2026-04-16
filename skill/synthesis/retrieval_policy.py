"""Deterministic retrieval-policy helpers for bounded coverage frontier probes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from skill.config.retrieval import (
    COVERAGE_FRONTIER_COMPLEMENTARY_SOURCES,
    COVERAGE_FRONTIER_MAX_PROBES,
    COVERAGE_FRONTIER_MIN_ALIGNMENT_TO_DEEPEN,
    COVERAGE_FRONTIER_MIN_REMAINING_SECONDS_TO_PROBE,
    COVERAGE_FRONTIER_PER_PROBE_TIMEOUT_SECONDS,
    ConcreteRoute,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.priority import score_query_alignment

CoverageFrontierDecision = Literal["grounded_success", "deepen", "insufficient_evidence"]


@dataclass(frozen=True)
class CoverageFrontierProbe:
    """A bounded probe/deepen candidate for complementary-route coverage."""

    source_id: str
    source_route: ConcreteRoute
    target_route: ConcreteRoute
    probe_query: str
    reason_code: str = "coverage_frontier"
    alignment_score: int = 0
    selected_evidence_id: str | None = None
    selected_title: str | None = None
    selected_url: str | None = None


def _probe_hit_identity(hit: RetrievalHit) -> str:
    normalized_title = "-".join(hit.title.lower().split()) if hit.title else "untitled"
    return f"{hit.source_id}:{normalized_title}:{hit.url}"


def has_budget_for_coverage_frontier_probe(
    *,
    remaining_request_seconds: float,
    min_remaining_seconds: float = COVERAGE_FRONTIER_MIN_REMAINING_SECONDS_TO_PROBE,
    per_probe_timeout_seconds: float = COVERAGE_FRONTIER_PER_PROBE_TIMEOUT_SECONDS,
) -> bool:
    """Return whether request budget can accommodate at least one bounded probe."""

    if COVERAGE_FRONTIER_MAX_PROBES <= 0 or per_probe_timeout_seconds <= 0:
        return False
    return remaining_request_seconds >= (min_remaining_seconds + per_probe_timeout_seconds)


def build_coverage_frontier_candidates(
    *,
    source_route: ConcreteRoute,
    probe_query: str,
    max_probes: int = COVERAGE_FRONTIER_MAX_PROBES,
) -> tuple[CoverageFrontierProbe, ...]:
    """Build deterministic complementary-route probe candidates."""

    if max_probes <= 0:
        return ()

    candidates: list[CoverageFrontierProbe] = []
    for (origin_route, target_route), source_ids in COVERAGE_FRONTIER_COMPLEMENTARY_SOURCES.items():
        if origin_route != source_route:
            continue
        for source_id in source_ids:
            candidates.append(
                CoverageFrontierProbe(
                    source_id=source_id,
                    source_route=source_route,
                    target_route=target_route,
                    probe_query=probe_query,
                    reason_code=(
                        f"{source_route}_to_{target_route}_coverage_frontier:{source_id}"
                    ),
                )
            )
    return tuple(candidates[:max_probes])


def select_coverage_frontier_winner(
    probes: tuple[CoverageFrontierProbe, ...],
    *,
    min_alignment_to_deepen: int = COVERAGE_FRONTIER_MIN_ALIGNMENT_TO_DEEPEN,
) -> CoverageFrontierProbe | None:
    """Pick the best aligned branch to deepen, if any."""

    eligible = [probe for probe in probes if probe.alignment_score >= min_alignment_to_deepen]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda probe: (
            probe.alignment_score,
            probe.selected_evidence_id or "",
            probe.selected_title or "",
            probe.selected_url or "",
            probe.source_id,
            probe.probe_query,
        ),
    )


def attach_probe_alignment(
    probe: CoverageFrontierProbe,
    *,
    query: str,
    hit: RetrievalHit,
) -> CoverageFrontierProbe:
    """Annotate a probe candidate with deterministic query-hit alignment metadata."""

    alignment_score = score_query_alignment(
        query,
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
    return replace(
        probe,
        alignment_score=alignment_score,
        selected_evidence_id=_probe_hit_identity(hit),
        selected_title=hit.title,
        selected_url=hit.url,
    )


def decide_coverage_frontier_sufficiency(
    *,
    has_grounded_local_answer: bool,
    aligned_supplemental_evidence_count: int,
    winner: CoverageFrontierProbe | None,
    min_alignment_to_deepen: int = COVERAGE_FRONTIER_MIN_ALIGNMENT_TO_DEEPEN,
) -> CoverageFrontierDecision:
    """Choose stop/deepen outcome after a bounded frontier pass."""

    if has_grounded_local_answer:
        return "grounded_success"
    if (
        aligned_supplemental_evidence_count > 0
        and winner is not None
        and winner.alignment_score >= min_alignment_to_deepen
    ):
        return "grounded_success"
    if winner is not None and winner.alignment_score >= min_alignment_to_deepen:
        return "deepen"
    return "insufficient_evidence"
