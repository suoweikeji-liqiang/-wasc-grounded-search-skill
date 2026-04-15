"""In-process cache for stable grounded answers."""

from __future__ import annotations

from dataclasses import dataclass

from skill.api.schema import AnswerResponse
from skill.orchestrator.normalize import normalize_query_text
from skill.orchestrator.retrieval_plan import RetrievalPlan

PIPELINE_CACHE_VERSION = "answer-cache-v1"


@dataclass(frozen=True)
class CachedAnswerEntry:
    response: AnswerResponse
    evidence_token_estimate: int
    answer_token_estimate: int | None
    retrieval_trace: tuple[dict[str, object], ...] = ()


class GroundedAnswerCache:
    def __init__(self, *, pipeline_version: str = PIPELINE_CACHE_VERSION) -> None:
        self.pipeline_version = pipeline_version
        self._entries: dict[str, CachedAnswerEntry] = {}

    def build_key(self, *, query: str, plan: RetrievalPlan) -> str:
        normalized_query = normalize_query_text(query)
        supplemental_route = plan.supplemental_route or "-"
        return (
            f"{self.pipeline_version}|{plan.route_label}|{plan.primary_route}|"
            f"{supplemental_route}|{normalized_query}"
        )

    def get(self, *, query: str, plan: RetrievalPlan) -> CachedAnswerEntry | None:
        entry = self._entries.get(self.build_key(query=query, plan=plan))
        if entry is None:
            return None
        return CachedAnswerEntry(
            response=entry.response.model_copy(deep=True),
            evidence_token_estimate=entry.evidence_token_estimate,
            answer_token_estimate=entry.answer_token_estimate,
            retrieval_trace=tuple(dict(item) for item in entry.retrieval_trace),
        )

    def put(
        self,
        *,
        query: str,
        plan: RetrievalPlan,
        response: AnswerResponse,
        evidence_token_estimate: int,
        answer_token_estimate: int | None,
        retrieval_trace: tuple[dict[str, object], ...] = (),
    ) -> None:
        self._entries[self.build_key(query=query, plan=plan)] = CachedAnswerEntry(
            response=response.model_copy(deep=True),
            evidence_token_estimate=evidence_token_estimate,
            answer_token_estimate=answer_token_estimate,
            retrieval_trace=tuple(dict(item) for item in retrieval_trace),
        )

    def clear(self) -> None:
        self._entries.clear()


ANSWER_CACHE = GroundedAnswerCache()
