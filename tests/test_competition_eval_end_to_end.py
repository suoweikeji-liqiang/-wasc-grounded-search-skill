"""End-to-end competition-style answer regressions using live default adapters."""

from __future__ import annotations

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
    api_entry.app.state.model_client = _NeverCalledModelClient()
    try:
        client = TestClient(api_entry.app)
        response = client.post("/answer", json={"query": query})
    finally:
        ANSWER_CACHE.clear()
        del api_entry.app.state.model_client

    assert response.status_code == 200
    return response.json()


def test_answer_endpoint_handles_competition_policy_change_query_with_two_sources() -> None:
    payload = _post_answer("2025年数据出境安全评估办法有哪些变化？")

    assert payload["route_label"] == "policy"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "变化" in merged
    assert any(term in merged for term in ("新增", "调整"))


def test_answer_endpoint_handles_competition_industry_trend_query_with_two_sources() -> None:
    payload = _post_answer("中国智能手机2026年出货量趋势")

    assert payload["route_label"] == "industry"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "出货" in merged
    assert "趋势" in merged


def test_answer_endpoint_handles_competition_academic_lookup_query_with_two_sources() -> None:
    payload = _post_answer("RAG chunking 最新论文综述")

    assert payload["route_label"] == "academic"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload).lower()
    assert "rag" in merged
    assert "chunking" in merged
    assert ("paper" in merged) or ("arxiv" in merged)


def test_answer_endpoint_handles_competition_policy_exemption_query() -> None:
    payload = _post_answer("促进和规范数据跨境流动规定中哪些场景可豁免？")

    assert payload["route_label"] == "policy"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 1

    merged = _merged_answer_text(payload)
    assert "豁免" in merged
    assert "场景" in merged


def test_answer_endpoint_handles_competition_academic_reranking_query() -> None:
    payload = _post_answer("retrieval reranking recent benchmark papers")

    assert payload["route_label"] == "academic"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload).lower()
    assert "reranking" in merged
    assert "benchmark" in merged
    assert "paper" in merged


def test_answer_endpoint_handles_competition_mixed_impact_query_with_two_sources() -> None:
    payload = _post_answer("AI Act 对开源模型和产业落地影响")

    assert payload["route_label"] == "mixed"
    assert payload["answer_status"] == "grounded_success"
    assert len(payload["sources"]) >= 2

    merged = _merged_answer_text(payload)
    assert "AI Act" in merged
    assert any(term in merged for term in ("开源模型", "产业落地"))
