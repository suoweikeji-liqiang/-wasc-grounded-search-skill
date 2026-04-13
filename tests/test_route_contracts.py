"""Offline routing contract regressions for Phase 1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from skill.api.entry import app
from skill.config.routes import ROUTE_SOURCE_FAMILIES

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "phase1_queries.json"
EXPECTED_RESPONSE_KEYS = {
    "route_label",
    "source_families",
    "primary_route",
    "supplemental_route",
    "browser_automation",
}
ALLOWED_ROUTE_LABELS = {"policy", "industry", "academic", "mixed"}
ALLOWED_CONCRETE_ROUTES = {"policy", "industry", "academic"}
AMBIGUOUS_MIXED_REASON_CATEGORIES = {
    "short_query",
    "low_signal",
    "precedence_tie_policy_over_academic",
    "precedence_tie_academic_over_industry",
    "ambiguous_tie_defaults_precedence",
}

ENGLISH_BENCHMARK_ROUTE_CASES = (
    {
        "query": "latest climate order version",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "latest methane registry update",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "industrial emissions guidance effective date",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "grounded search evidence packing paper",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "evidence normalization benchmark paper",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "latency-aware retrieval paper",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "semiconductor packaging capacity forecast 2026",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "battery recycling market share 2025",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "autonomous driving policy impact on industry",
        "route_label": "mixed",
        "primary_route": "policy",
        "supplemental_route": "industry",
    },
    {
        "query": "AI chip export controls effect on academic research",
        "route_label": "mixed",
        "primary_route": "policy",
        "supplemental_route": "academic",
    },
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def phase1_fixtures() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture",
    json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
    ids=lambda item: item["name"],
)
def test_route_contract_per_fixture(client: TestClient, fixture: dict[str, Any]) -> None:
    response = client.post("/route", json={"query": fixture["query"]})
    assert response.status_code == 200

    payload = response.json()
    assert set(payload.keys()) == EXPECTED_RESPONSE_KEYS
    assert payload["route_label"] in ALLOWED_ROUTE_LABELS
    assert payload["primary_route"] in ALLOWED_CONCRETE_ROUTES
    assert payload["primary_route"] != "mixed"
    assert payload["supplemental_route"] in ALLOWED_CONCRETE_ROUTES | {None}
    assert payload["browser_automation"] == "disabled"

    assert payload["route_label"] == fixture["expected_route_label"]
    assert payload["primary_route"] == fixture["expected_primary_route"]
    assert payload["supplemental_route"] == fixture["expected_supplemental_route"]

    expected_families = fixture["expected_source_families_contains"]
    observed_families = payload["source_families"]
    last_index = -1
    for family in expected_families:
        assert family in observed_families
        current_index = observed_families.index(family)
        assert current_index > last_index
        last_index = current_index


@pytest.mark.parametrize(
    "fixture_name", ["precedence_policy_over_academic", "precedence_academic_over_industry"]
)
def test_precedence_regressions_use_concrete_primary_route(
    client: TestClient,
    phase1_fixtures: list[dict[str, Any]],
    fixture_name: str,
) -> None:
    fixture = next(item for item in phase1_fixtures if item["name"] == fixture_name)
    payload = client.post("/route", json={"query": fixture["query"]}).json()

    assert payload["route_label"] == "mixed"
    assert payload["primary_route"] == fixture["expected_primary_route"]
    assert payload["supplemental_route"] is None


def test_low_signal_query_regression(client: TestClient, phase1_fixtures: list[dict[str, Any]]) -> None:
    fixture = next(item for item in phase1_fixtures if item["name"] == "mixed_low_signal")
    payload = client.post("/route", json={"query": fixture["query"]}).json()

    assert payload["route_label"] == "mixed"
    assert payload["primary_route"] in ALLOWED_CONCRETE_ROUTES
    assert payload["supplemental_route"] is None


def test_short_query_regression(client: TestClient, phase1_fixtures: list[dict[str, Any]]) -> None:
    fixture = next(item for item in phase1_fixtures if item["name"] == "mixed_short")
    payload = client.post("/route", json={"query": fixture["query"]}).json()

    assert payload["route_label"] == "mixed"
    assert payload["primary_route"] in ALLOWED_CONCRETE_ROUTES
    assert payload["supplemental_route"] is None


@pytest.mark.parametrize(
    "fixture",
    json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
    ids=lambda item: item["name"],
)
def test_browser_automation_is_always_disabled(
    client: TestClient, fixture: dict[str, Any]
) -> None:
    payload = client.post("/route", json={"query": fixture["query"]}).json()
    assert payload["browser_automation"] == "disabled"


@pytest.mark.parametrize(
    "fixture",
    [
        item
        for item in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        if item["reason_category"] in AMBIGUOUS_MIXED_REASON_CATEGORIES
    ],
    ids=lambda item: item["name"],
)
def test_ambiguous_mixed_contract_uses_concrete_primary_family_table(
    client: TestClient, fixture: dict[str, Any]
) -> None:
    payload = client.post("/route", json={"query": fixture["query"]}).json()

    assert payload["route_label"] == "mixed"
    assert payload["primary_route"] in ALLOWED_CONCRETE_ROUTES
    assert payload["supplemental_route"] is None
    assert payload["source_families"] == list(ROUTE_SOURCE_FAMILIES[payload["primary_route"]])


@pytest.mark.parametrize("case", ENGLISH_BENCHMARK_ROUTE_CASES, ids=lambda case: case["query"])
def test_english_benchmark_queries_route_to_expected_domains(
    client: TestClient,
    case: dict[str, str | None],
) -> None:
    payload = client.post("/route", json={"query": case["query"]}).json()

    assert payload["route_label"] == case["route_label"]
    assert payload["primary_route"] == case["primary_route"]
    assert payload["supplemental_route"] == case["supplemental_route"]
