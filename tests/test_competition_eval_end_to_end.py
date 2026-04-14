"""End-to-end competition-style answer regressions using fixture-mode adapters."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from skill.synthesis.cache import ANSWER_CACHE


class _NeverCalledModelClient:
    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        raise AssertionError("competition regression should stay on grounded local paths")


def _merged_answer_text(payload: dict[str, object]) -> str:
    parts: list[str] = [str(payload["conclusion"])]
    parts.extend(
        str(item["statement"])
        for item in payload["key_points"]
        if isinstance(item, dict) and "statement" in item
    )
    parts.extend(
        str(item["title"])
        for item in payload["sources"]
        if isinstance(item, dict) and "title" in item
    )
    return "\n".join(parts)


def _post_answer(query: str) -> dict[str, object]:
    import skill.api.entry as api_entry

    ANSWER_CACHE.clear()
    previous_mode = os.environ.get("WASC_RETRIEVAL_MODE")
    os.environ["WASC_RETRIEVAL_MODE"] = "fixture"
    api_entry.app.state.model_client = _NeverCalledModelClient()
    try:
        client = TestClient(api_entry.app)
        response = client.post("/answer", json={"query": query})
    finally:
        ANSWER_CACHE.clear()
        if previous_mode is None:
            os.environ.pop("WASC_RETRIEVAL_MODE", None)
        else:
            os.environ["WASC_RETRIEVAL_MODE"] = previous_mode
        del api_entry.app.state.model_client

    assert response.status_code == 200
    return response.json()


def test_answer_endpoint_handles_competition_policy_change_query_with_two_sources() -> None:
    payload = _post_answer(
        "\u0032\u0030\u0032\u0035\u5e74\u6570\u636e\u51fa\u5883\u5b89\u5168\u8bc4\u4f30\u529e\u6cd5\u6709\u54ea\u4e9b\u53d8\u5316\uff1f"
    )

    assert payload["route_label"] == "policy"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "\u53d8\u5316" in merged
    assert any(term in merged for term in ("\u65b0\u589e", "\u8c03\u6574"))


def test_answer_endpoint_handles_competition_industry_trend_query_with_two_sources() -> None:
    payload = _post_answer(
        "\u4e2d\u56fd\u667a\u80fd\u624b\u673a\u0032\u0030\u0032\u0036\u5e74\u51fa\u8d27\u91cf\u8d8b\u52bf"
    )

    assert payload["route_label"] == "industry"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "\u51fa\u8d27" in merged
    assert "\u8d8b\u52bf" in merged


def test_answer_endpoint_handles_competition_academic_lookup_query_with_two_sources() -> None:
    payload = _post_answer("RAG chunking \u6700\u65b0\u8bba\u6587\u7efc\u8ff0")

    assert payload["route_label"] == "academic"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload).lower()
    assert "rag" in merged
    assert "chunking" in merged
    assert ("paper" in merged) or ("arxiv" in merged)


def test_answer_endpoint_handles_competition_policy_exemption_query() -> None:
    payload = _post_answer(
        "\u4fc3\u8fdb\u548c\u89c4\u8303\u6570\u636e\u8de8\u5883\u6d41\u52a8\u89c4\u5b9a\u4e2d\u54ea\u4e9b\u573a\u666f\u53ef\u8c41\u514d\uff1f"
    )

    assert payload["route_label"] == "policy"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 1

    merged = _merged_answer_text(payload)
    assert "\u8c41\u514d" in merged
    assert "\u573a\u666f" in merged


def test_answer_endpoint_handles_competition_academic_reranking_query() -> None:
    payload = _post_answer("retrieval reranking recent benchmark papers")

    assert payload["route_label"] == "academic"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload).lower()
    assert "reranking" in merged
    assert "benchmark" in merged
    assert "paper" in merged


def test_answer_endpoint_handles_competition_academic_agent_research_query_without_extra_uncertainty() -> None:
    payload = _post_answer("LLM agent planning \u6700\u65b0\u7814\u7a76")

    assert payload["route_label"] == "academic"
    assert payload["answer_status"] == "grounded_success"
    assert payload["uncertainty_notes"] == []

    merged = _merged_answer_text(payload)
    assert "\u7814\u7a76" in merged
    assert "paper" in merged.lower()


def test_answer_endpoint_handles_competition_mixed_impact_query_with_two_sources() -> None:
    payload = _post_answer("AI Act \u5bf9\u5f00\u6e90\u6a21\u578b\u548c\u4ea7\u4e1a\u843d\u5730\u5f71\u54cd")

    assert payload["route_label"] == "mixed"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "AI Act" in merged
    assert any(term in merged for term in ("\u5f00\u6e90\u6a21\u578b", "\u4ea7\u4e1a\u843d\u5730"))
