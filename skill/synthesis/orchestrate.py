"""End-to-end grounded answer orchestration."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import replace

from skill.api.schema import AnswerResponse, RetrieveCanonicalEvidenceItem, RetrieveResponse
from skill.evidence.models import CanonicalEvidence, EvidenceSlice, LinkedVariant, RawEvidenceRecord
from skill.orchestrator.budget import (
    AnswerExecutionResult,
    RuntimeBudget,
    RuntimeTrace,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.orchestrate import Adapter, execute_retrieval_pipeline
from skill.synthesis.citation_check import validate_answer_citations
from skill.synthesis.generator import ModelClient, generate_answer_draft
from skill.synthesis.prompt import build_grounded_answer_prompt
from skill.synthesis.state import determine_answer_status
from skill.synthesis.uncertainty import build_uncertainty_notes


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
    return AnswerResponse(
        answer_status="insufficient_evidence",
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        route_label=retrieval_response.route_label,
        primary_route=retrieval_response.primary_route,
        supplemental_route=retrieval_response.supplemental_route,
        browser_automation="disabled",
        conclusion="Available runtime budget was insufficient to complete grounded synthesis.",
        key_points=[],
        sources=[],
        uncertainty_notes=[f"Budget enforcement: {reason}", *uncertainty_notes],
        gaps=list(retrieval_response.gaps),
    )


def _build_answer_response(
    retrieval_response: RetrieveResponse,
    canonical_evidence: tuple[CanonicalEvidence, ...],
    draft,
) -> AnswerResponse:
    citation_result = validate_answer_citations(draft, canonical_evidence)
    answer_status = determine_answer_status(
        retrieval_status=retrieval_response.status,
        failure_reason=retrieval_response.failure_reason,
        canonical_evidence_count=len(canonical_evidence),
        grounded_key_point_count=citation_result.grounded_key_point_count,
        total_key_point_count=citation_result.total_key_point_count,
    )
    uncertainty_notes = build_uncertainty_notes(
        retrieval_status=retrieval_response.status,
        gaps=tuple(retrieval_response.gaps),
        evidence_clipped=retrieval_response.evidence_clipped,
        evidence_pruned=retrieval_response.evidence_pruned,
        canonical_evidence=canonical_evidence,
        citation_issues=citation_result.issues,
    )

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

    conclusion = draft.conclusion
    if answer_status == "insufficient_evidence":
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
    retrieval_plan = replace(
        plan,
        overall_deadline_seconds=min(
            plan.overall_deadline_seconds,
            budget.retrieval_deadline_seconds,
        ),
    )
    retrieval_response = await execute_retrieval_pipeline(
        plan=retrieval_plan,
        query=query,
        adapter_registry=adapter_registry,
    )
    retrieval_elapsed_seconds = time.perf_counter() - started_at
    canonical_evidence = tuple(
        _rehydrate_canonical_evidence(item)
        for item in retrieval_response.canonical_evidence
    )
    evidence_token_estimate = _estimate_evidence_tokens(canonical_evidence)
    budget_exhausted_phase: str | None = None

    if retrieval_response.status == "failure_gaps" and not canonical_evidence:
        response = _build_retrieval_failure_response(
            retrieval_response,
            canonical_evidence,
        )
        answer_token_estimate = _estimate_response_tokens(response)
        return AnswerExecutionResult(
            response=response,
            runtime_trace=_build_runtime_trace(
                request_id=request_id,
                response=response,
                retrieval_elapsed_seconds=retrieval_elapsed_seconds,
                synthesis_elapsed_seconds=0.0,
                evidence_token_estimate=evidence_token_estimate,
                answer_token_estimate=answer_token_estimate,
                runtime_budget=budget,
                budget_exhausted_phase=None,
            ),
        )

    remaining_synthesis_seconds = budget.remaining_synthesis_seconds(
        retrieval_elapsed_seconds=retrieval_elapsed_seconds,
    )
    if remaining_synthesis_seconds <= 0:
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            reason="no synthesis time remained within the request budget.",
        )
        answer_token_estimate = _estimate_response_tokens(response)
        return AnswerExecutionResult(
            response=response,
            runtime_trace=_build_runtime_trace(
                request_id=request_id,
                response=response,
                retrieval_elapsed_seconds=retrieval_elapsed_seconds,
                synthesis_elapsed_seconds=0.0,
                evidence_token_estimate=evidence_token_estimate,
                answer_token_estimate=answer_token_estimate,
                runtime_budget=budget,
                budget_exhausted_phase="synthesis",
            ),
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
    except TimeoutError:
        budget_exhausted_phase = "synthesis"
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            reason="grounded synthesis exceeded the remaining request budget.",
        )
        synthesis_elapsed_seconds = time.perf_counter() - synthesis_started_at
        answer_token_estimate = _estimate_response_tokens(response)
        return AnswerExecutionResult(
            response=response,
            runtime_trace=_build_runtime_trace(
                request_id=request_id,
                response=response,
                retrieval_elapsed_seconds=retrieval_elapsed_seconds,
                synthesis_elapsed_seconds=synthesis_elapsed_seconds,
                evidence_token_estimate=evidence_token_estimate,
                answer_token_estimate=answer_token_estimate,
                runtime_budget=budget,
                budget_exhausted_phase=budget_exhausted_phase,
            ),
        )

    response = _build_answer_response(
        retrieval_response,
        canonical_evidence,
        draft,
    )
    synthesis_elapsed_seconds = time.perf_counter() - synthesis_started_at
    answer_token_estimate = _estimate_response_tokens(response)

    if answer_token_estimate > budget.answer_token_budget:
        budget_exhausted_phase = "answer_tokens"
        response = _build_budget_enforced_response(
            retrieval_response,
            canonical_evidence,
            reason="grounded output would exceed the answer token budget.",
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
            runtime_budget=budget,
            budget_exhausted_phase=budget_exhausted_phase,
        ),
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
