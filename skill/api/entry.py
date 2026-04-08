"""FastAPI entrypoint for Phase 1 routing API."""

from __future__ import annotations

from fastapi import FastAPI

from skill.api.schema import RouteRequest, RouteResponse
from skill.orchestrator.intent import classify_query
from skill.orchestrator.planner import plan_route

app = FastAPI(title="WASC Phase 1 Routing API", version="0.1.0")


@app.post("/route", response_model=RouteResponse)
def route_query(payload: RouteRequest) -> RouteResponse:
    classification = classify_query(payload.query)
    return plan_route(classification)
