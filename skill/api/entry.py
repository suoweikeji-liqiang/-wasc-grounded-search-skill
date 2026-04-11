"""FastAPI entrypoint for Phase 1 routing API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI

from skill.api.schema import RetrieveRequest, RetrieveResponse, RouteRequest, RouteResponse
from skill.orchestrator.intent import classify_query
from skill.orchestrator.planner import plan_route
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.adapters.academic_arxiv import search as academic_arxiv_search
from skill.retrieval.adapters.academic_semantic_scholar import (
    search as academic_semantic_scholar_search,
)
from skill.retrieval.adapters.industry_ddgs import search as industry_ddgs_search
from skill.retrieval.adapters.policy_official_registry import (
    search as policy_official_registry_search,
)
from skill.retrieval.adapters.policy_official_web_allowlist import (
    search as policy_official_web_allowlist_search,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.orchestrate import execute_retrieval_pipeline

app = FastAPI(title="WASC Phase 1 Routing API", version="0.1.0")

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]


def _default_adapter_registry() -> Mapping[str, Adapter]:
    return {
        "policy_official_registry": policy_official_registry_search,
        "policy_official_web_allowlist_fallback": policy_official_web_allowlist_search,
        "academic_semantic_scholar": academic_semantic_scholar_search,
        "academic_arxiv": academic_arxiv_search,
        "industry_ddgs": industry_ddgs_search,
    }


@app.post("/route", response_model=RouteResponse)
def route_query(payload: RouteRequest) -> RouteResponse:
    classification = classify_query(payload.query)
    return plan_route(classification)


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_query(payload: RetrieveRequest) -> RetrieveResponse:
    classification = classify_query(payload.query)
    retrieval_plan = build_retrieval_plan(classification)
    return await execute_retrieval_pipeline(
        plan=retrieval_plan,
        query=payload.query,
        adapter_registry=_default_adapter_registry(),
    )
