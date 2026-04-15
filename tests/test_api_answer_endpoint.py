"""Phase 4 answer endpoint regressions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from skill.api.schema import AnswerResponse


def _make_answer_response(answer_status: str) -> AnswerResponse:
    return AnswerResponse(
        answer_status=answer_status,
        retrieval_status="failure_gaps" if answer_status == "retrieval_failure" else "success",
        failure_reason="timeout" if answer_status == "retrieval_failure" else None,
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        conclusion="Retrieval failed before a grounded answer could be produced."
        if answer_status == "retrieval_failure"
        else "Grounded answer available.",
        key_points=[]
        if answer_status == "retrieval_failure"
        else [
            {
                "key_point_id": "kp-1",
                "statement": "The Climate Order takes effect on May 1, 2026.",
                "citations": [
                    {
                        "evidence_id": "policy-1",
                        "source_record_id": "policy-1-slice-1",
                        "source_url": "https://www.gov.cn/policy/climate-order-2026",
                        "quote_text": "The Climate Order takes effect on May 1, 2026."
                    }
                ],
            }
        ],
        sources=[]
        if answer_status == "retrieval_failure"
        else [
            {
                "evidence_id": "policy-1",
                "title": "Climate Order 2026",
                "url": "https://www.gov.cn/policy/climate-order-2026",
            }
        ],
        uncertainty_notes=[]
        if answer_status == "grounded_success"
        else ["Citation validation: one key point could not be grounded."],
        gaps=[]
        if answer_status != "retrieval_failure"
        else ["Official registry timed out."],
    )


def test_answer_api_endpoint_returns_grounded_success(monkeypatch) -> None:
    import skill.api.entry as api_entry

    async def _fake_execute_answer_pipeline(**_: object) -> AnswerResponse:
        return _make_answer_response("grounded_success")

    monkeypatch.setattr(api_entry, "execute_answer_pipeline", _fake_execute_answer_pipeline)

    client = TestClient(api_entry.app)
    response = client.post("/answer", json={"query": "latest climate order version"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_status"] == "grounded_success"
    assert payload["conclusion"]
    assert payload["key_points"]
    assert payload["sources"]
    assert payload["browser_automation"] == "disabled"
    assert "total_token_estimate" not in payload
    assert "token_budget" not in payload


def test_answer_api_endpoint_returns_insufficient_evidence(monkeypatch) -> None:
    import skill.api.entry as api_entry

    async def _fake_execute_answer_pipeline(**_: object) -> AnswerResponse:
        return _make_answer_response("insufficient_evidence")

    monkeypatch.setattr(api_entry, "execute_answer_pipeline", _fake_execute_answer_pipeline)

    client = TestClient(api_entry.app)
    response = client.post("/answer", json={"query": "grounded evidence packing paper"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_status"] == "insufficient_evidence"
    assert payload["uncertainty_notes"]
    assert payload["route_label"] == "policy"
    assert payload["primary_route"] == "policy"


def test_answer_api_endpoint_returns_retrieval_failure(monkeypatch) -> None:
    import skill.api.entry as api_entry

    async def _fake_execute_answer_pipeline(**_: object) -> AnswerResponse:
        return _make_answer_response("retrieval_failure")

    monkeypatch.setattr(api_entry, "execute_answer_pipeline", _fake_execute_answer_pipeline)

    client = TestClient(api_entry.app)
    response = client.post("/answer", json={"query": "latest methane registry update"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_status"] == "retrieval_failure"
    assert payload["gaps"]
    assert payload["key_points"] == []
    assert payload["sources"] == []


def test_default_model_client_accepts_legacy_minimax_key_name(monkeypatch) -> None:
    import skill.api.entry as api_entry

    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MINIMAX_KEY", "legacy-key")

    client = api_entry._default_model_client()

    assert client.api_key == "legacy-key"


def test_default_model_client_loads_repo_dotenv_when_process_env_is_empty(monkeypatch) -> None:
    import os

    import skill.api.entry as api_entry

    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_KEY", raising=False)

    observed: dict[str, int] = {"calls": 0}

    def _fake_load_repo_dotenv() -> dict[str, str]:
        observed["calls"] += 1
        os.environ["MINIMAX_KEY"] = "dotenv-key"
        return {"MINIMAX_KEY": "dotenv-key"}

    monkeypatch.setattr(api_entry, "load_repo_dotenv", _fake_load_repo_dotenv)

    client = api_entry._default_model_client()

    assert observed["calls"] == 1
    assert client.api_key == "dotenv-key"


def test_default_adapter_registry_uses_live_adapter_functions_by_default(monkeypatch) -> None:
    import skill.api.entry as api_entry

    monkeypatch.delenv("WASC_RETRIEVAL_MODE", raising=False)

    registry = api_entry._default_adapter_registry()

    assert registry["policy_official_registry"].__name__ == "search_live"
    assert registry["policy_official_web_allowlist_fallback"].__name__ == "search_live"
    assert registry["academic_asta_mcp"].__name__ == "search_live"
    assert registry["academic_semantic_scholar"].__name__ == "search_live"
    assert registry["academic_arxiv"].__name__ == "search_live"
    assert registry["industry_ddgs"].__name__ == "search_live"


def test_default_adapter_registry_can_force_fixture_mode(monkeypatch) -> None:
    import skill.api.entry as api_entry

    monkeypatch.setenv("WASC_RETRIEVAL_MODE", "fixture")

    registry = api_entry._default_adapter_registry()

    assert registry["policy_official_registry"].__name__ == "search_fixture"
    assert registry["policy_official_web_allowlist_fallback"].__name__ == "search_fixture"
    assert registry["academic_asta_mcp"].__name__ == "search_fixture"
    assert registry["academic_semantic_scholar"].__name__ == "search_fixture"
    assert registry["academic_arxiv"].__name__ == "search_fixture"
    assert registry["industry_ddgs"].__name__ == "search_fixture"
