"""FastAPI entrypoint for the WASC search Skill API."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI

from skill.api.schema import (
    AnswerRequest,
    AnswerResponse,
    RetrieveRequest,
    RetrieveResponse,
    RouteRequest,
    RouteResponse,
)
from skill.config.env import load_repo_dotenv
from skill.config.live_retrieval import LiveRetrievalConfig
from skill.orchestrator.budget import AnswerExecutionResult, RuntimeBudget
from skill.orchestrator.intent import classify_query
from skill.orchestrator.planner import plan_route
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.adapters.academic_asta_mcp import (
    search_fixture as academic_asta_mcp_search_fixture,
)
from skill.retrieval.adapters.academic_asta_mcp import search_live as academic_asta_mcp_search_live
from skill.retrieval.adapters.academic_arxiv import (
    search_fixture as academic_arxiv_search_fixture,
)
from skill.retrieval.adapters.academic_arxiv import search_live as academic_arxiv_search_live
from skill.retrieval.adapters.academic_semantic_scholar import (
    search_fixture as academic_semantic_scholar_search_fixture,
)
from skill.retrieval.adapters.academic_semantic_scholar import (
    search_live as academic_semantic_scholar_search_live,
)
from skill.retrieval.adapters.industry_ddgs import search_fixture as industry_ddgs_search_fixture
from skill.retrieval.adapters.industry_ddgs import search_live as industry_ddgs_search_live
from skill.retrieval.adapters.policy_official_registry import (
    search_fixture as policy_official_registry_search_fixture,
)
from skill.retrieval.adapters.policy_official_registry import (
    search_live as policy_official_registry_search_live,
)
from skill.retrieval.adapters.policy_official_web_allowlist import (
    search_fixture as policy_official_web_allowlist_search_fixture,
)
from skill.retrieval.adapters.policy_official_web_allowlist import (
    search_live as policy_official_web_allowlist_search_live,
)
from skill.retrieval.models import RetrievalHit
from skill.retrieval.orchestrate import execute_retrieval_pipeline
from skill.synthesis.generator import MiniMaxTextClient
from skill.synthesis.orchestrate import execute_answer_pipeline_with_trace

execute_answer_pipeline = execute_answer_pipeline_with_trace

app = FastAPI(title="WASC High-Precision Search Skill API", version="1.0.0")

Adapter = Callable[[str], Awaitable[list[RetrievalHit]]]


def _default_adapter_registry() -> Mapping[str, Adapter]:
    load_repo_dotenv()
    config = LiveRetrievalConfig.from_env()
    if config.mode == "fixture":
        return {
            "policy_official_registry": policy_official_registry_search_fixture,
            "policy_official_web_allowlist_fallback": policy_official_web_allowlist_search_fixture,
            "academic_asta_mcp": academic_asta_mcp_search_fixture,
            "academic_semantic_scholar": academic_semantic_scholar_search_fixture,
            "academic_arxiv": academic_arxiv_search_fixture,
            "industry_ddgs": industry_ddgs_search_fixture,
        }
    return {
        "policy_official_registry": policy_official_registry_search_live,
        "policy_official_web_allowlist_fallback": policy_official_web_allowlist_search_live,
        "academic_asta_mcp": academic_asta_mcp_search_live,
        "academic_semantic_scholar": academic_semantic_scholar_search_live,
        "academic_arxiv": academic_arxiv_search_live,
        "industry_ddgs": industry_ddgs_search_live,
    }


def _default_model_client() -> MiniMaxTextClient:
    load_repo_dotenv()
    api_key = os.getenv("MINIMAX_API_KEY", "") or os.getenv("MINIMAX_KEY", "")
    return MiniMaxTextClient(api_key=api_key)


@app.post("/route", response_model=RouteResponse)
def route_query(payload: RouteRequest) -> RouteResponse:
    classification = classify_query(payload.query)
    return plan_route(classification)


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_query(payload: RetrieveRequest) -> RetrieveResponse:
    classification = classify_query(payload.query)
    retrieval_plan = build_retrieval_plan(classification, query=payload.query)
    return await execute_retrieval_pipeline(
        plan=retrieval_plan,
        query=payload.query,
        adapter_registry=_default_adapter_registry(),
    )


@app.post("/answer", response_model=AnswerResponse)
async def answer_query(payload: AnswerRequest) -> AnswerResponse:
    classification = classify_query(payload.query)
    retrieval_plan = build_retrieval_plan(classification, query=payload.query)
    adapter_registry = getattr(app.state, "adapter_registry", None) or _default_adapter_registry()
    model_client = getattr(app.state, "model_client", None) or _default_model_client()
    result = await execute_answer_pipeline(
        plan=retrieval_plan,
        query=payload.query,
        adapter_registry=adapter_registry,
        model_client=model_client,
        runtime_budget=RuntimeBudget.from_env(),
    )
    if isinstance(result, AnswerExecutionResult):
        app.state.last_runtime_trace = result.runtime_trace
        return result.response
    return result
