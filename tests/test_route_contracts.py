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
HIDDEN_SMOKE_FIXTURE_PATH = Path(__file__).with_name("fixtures") / "benchmark_hidden_style_smoke_cases.json"
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
    {
        "query": "NIS2 Directive transposition deadline adopt publish national measures official text",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "2025 retrieval-augmented generation citation grounding evaluation dataset factuality attribution",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "TSMC 2025 capex guidance range official earnings materials",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "NIST FIPS 203 ML-KEM-768 public key private key ciphertext shared secret byte lengths table",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "RFC 9700 OAuth 2.1 legacy authorization flows grant types removed discouraged sections",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "2025 2026 post-training RLHF alternatives DPO IPO KTO preference optimization comparison papers",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "NVIDIA fiscal 2026 Form 10-K risk factors supply chain export controls",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "FR reglement UE 2024 1689 definition systeme d IA article officiel",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "FCC Cyber Trust Mark minimum security requirements eligibility scope and ETSI EN 303 645 mapping with vendor readiness page",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "SEC cybersecurity disclosure rules Form 8-K Item 1.05 timing annual disclosure expectations and company 10-K 8-K language updates",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "EU AI Act GPAI transparency documentation obligations official text and Commission guidance cross-check with industry model card AI Act readiness",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "EU Battery Regulation 2023 1542 carbon footprint declaration battery passport due diligence deadlines and battery pass pilot manufacturer announcement",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "EU Data Act application date connected products data holder obligations vendor API contract update and academic legal commentary trade-secret safeguards",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
)

COMPETITION_STYLE_ROUTE_CASES = (
    {
        "query": "\u0032\u0030\u0032\u0035\u5e74\u4e2a\u4eba\u4fe1\u606f\u51fa\u5883\u8ba4\u8bc1\u529e\u6cd5\u4fee\u8ba2\u4e86\u54ea\u4e9b\u6761\u6b3e",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "\u0032\u0030\u0032\u0036\u5e74AI\u670d\u52a1\u5668GPU\u5e02\u573a\u4efd\u989d\u9884\u6d4b",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "LLM agent planning \u6700\u65b0\u7814\u7a76",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd",
        "route_label": "mixed",
        "primary_route": "policy",
        "supplemental_route": "industry",
    },
)

LEGACY_EXPLICIT_CROSS_DOMAIN_CASES = (
    {
        "query": "\u7814\u7a76\u4e0e\u76d1\u7ba1\u534f\u540c\u6846\u67b6",
        "route_label": "mixed",
        "primary_route": "policy",
        "supplemental_route": "academic",
    },
)

HIDDEN_STYLE_SMOKE_ROUTE_CASES = (
    {
        "query": "\u81ea\u52a8\u9a7e\u9a76\u8bd5\u70b9\u76d1\u7ba1\u529e\u6cd5\u4ec0\u4e48\u65f6\u5019\u5b9e\u65bd",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "\u667a\u80fd\u7f51\u8054\u6c7d\u8f66 \u8bd5\u70b9 \u76d1\u7ba1 \u901a\u77e5",
        "route_label": "policy",
        "primary_route": "policy",
        "supplemental_route": None,
    },
    {
        "query": "\u6709\u54ea\u4e9b grounded search evidence packing \u8bba\u6587",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "\u591a\u6e90 evidence ranking benchmark \u8bba\u6587",
        "route_label": "academic",
        "primary_route": "academic",
        "supplemental_route": None,
    },
    {
        "query": "advanced packaging capacity outlook 2026",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "\u52a8\u529b\u7535\u6c60\u56de\u6536\u5e02\u573a\u4efd\u989d\u9884\u6d4b",
        "route_label": "industry",
        "primary_route": "industry",
        "supplemental_route": None,
    },
    {
        "query": "\u81ea\u52a8\u9a7e\u9a76\u8bd5\u70b9\u76d1\u7ba1\u53d8\u5316\u5bf9\u4ea7\u4e1a\u6295\u8d44\u5f71\u54cd",
        "route_label": "mixed",
        "primary_route": "policy",
        "supplemental_route": "industry",
    },
    {
        "query": "AI chip export controls \u5bf9 academic research \u5f71\u54cd",
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
    assert payload["supplemental_route"] == fixture["expected_supplemental_route"]


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
    assert payload["supplemental_route"] == fixture["expected_supplemental_route"]

    expected_families = list(ROUTE_SOURCE_FAMILIES[payload["primary_route"]])
    if payload["supplemental_route"] is not None:
        expected_families.extend(ROUTE_SOURCE_FAMILIES[payload["supplemental_route"]])

    assert payload["source_families"] == list(dict.fromkeys(expected_families))


@pytest.mark.parametrize("case", ENGLISH_BENCHMARK_ROUTE_CASES, ids=lambda case: case["query"])
def test_english_benchmark_queries_route_to_expected_domains(
    client: TestClient,
    case: dict[str, str | None],
) -> None:
    payload = client.post("/route", json={"query": case["query"]}).json()

    assert payload["route_label"] == case["route_label"]
    assert payload["primary_route"] == case["primary_route"]
    assert payload["supplemental_route"] == case["supplemental_route"]


@pytest.mark.parametrize("case", COMPETITION_STYLE_ROUTE_CASES, ids=lambda case: case["query"])
def test_competition_style_queries_route_to_expected_domains(
    client: TestClient,
    case: dict[str, str | None],
) -> None:
    payload = client.post("/route", json={"query": case["query"]}).json()

    assert payload["route_label"] == case["route_label"]
    assert payload["primary_route"] == case["primary_route"]
    assert payload["supplemental_route"] == case["supplemental_route"]


@pytest.mark.parametrize("case", LEGACY_EXPLICIT_CROSS_DOMAIN_CASES, ids=lambda case: case["query"])
def test_legacy_explicit_cross_domain_markers_still_route_correctly(
    client: TestClient,
    case: dict[str, str | None],
) -> None:
    payload = client.post("/route", json={"query": case["query"]}).json()

    assert payload["route_label"] == case["route_label"]
    assert payload["primary_route"] == case["primary_route"]
    assert payload["supplemental_route"] == case["supplemental_route"]


def test_hidden_style_smoke_manifest_stays_route_aligned() -> None:
    payload = json.loads(HIDDEN_SMOKE_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert [item["query"] for item in payload] == [
        case["query"] for case in HIDDEN_STYLE_SMOKE_ROUTE_CASES
    ]
    assert [item["expected_route"] for item in payload] == [
        case["route_label"] for case in HIDDEN_STYLE_SMOKE_ROUTE_CASES
    ]


@pytest.mark.parametrize("case", HIDDEN_STYLE_SMOKE_ROUTE_CASES, ids=lambda case: case["query"])
def test_hidden_style_smoke_queries_route_to_expected_domains(
    client: TestClient,
    case: dict[str, str | None],
) -> None:
    payload = client.post("/route", json={"query": case["query"]}).json()

    assert payload["route_label"] == case["route_label"]
    assert payload["primary_route"] == case["primary_route"]
    assert payload["supplemental_route"] == case["supplemental_route"]
