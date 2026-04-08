from fastapi.testclient import TestClient

from skill.api.entry import app


def test_route_api_contract_mixed_and_ambiguous() -> None:
    client = TestClient(app)

    response = client.post("/route", json={"query": "自动驾驶政策对行业影响"})
    data = response.json()
    assert response.status_code == 200
    assert data["route_label"] == "mixed"
    assert data["primary_route"] in {"policy", "industry", "academic"}
    assert data["supplemental_route"] in {"policy", "industry", "academic"}
    assert data["browser_automation"] == "disabled"
    assert isinstance(data["source_families"], list) and len(data["source_families"]) >= 1

    ambiguous = client.post("/route", json={"query": "AI"})
    ambiguous_data = ambiguous.json()
    assert ambiguous.status_code == 200
    assert ambiguous_data["route_label"] == "mixed"
    assert ambiguous_data["primary_route"] == "policy"
    assert ambiguous_data["supplemental_route"] is None
