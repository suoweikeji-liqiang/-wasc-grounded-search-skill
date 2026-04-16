"""Judge packet export regressions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from skill.benchmark.models import BenchmarkCase
from skill.orchestrator.intent import ClassificationResult
from skill.retrieval.models import RetrievalHit
from skill.synthesis.cache import ANSWER_CACHE


def _policy_classification(_query: str) -> ClassificationResult:
    return ClassificationResult(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        reason_code="policy_hit",
        scores={"policy": 4, "academic": 0, "industry": 0},
    )


async def _policy_adapter(_: str) -> list[RetrievalHit]:
    return [
        RetrievalHit(
            source_id="policy_official_registry",
            title="Climate Order 2026",
            url="https://www.gov.cn/policy/climate-order-2026",
            snippet="The Climate Order takes effect on May 1, 2026.",
            credibility_tier="official_government",
            authority="State Council",
            jurisdiction="CN",
            publication_date="2026-04-01",
            effective_date="2026-05-01",
            version="2026-04 edition",
        )
    ]


class _NeverCalledModelClient:
    def generate_text(self, prompt: str, timeout_seconds: float | None = None) -> str:
        raise AssertionError("policy fast path should skip generation")


def test_export_judge_packets_uses_answer_side_evidence_materials(
    monkeypatch,
    tmp_path,
) -> None:
    import skill.api.entry as api_entry

    from skill.benchmark.judge_packets import export_judge_packets

    ANSWER_CACHE.clear()
    adapter_call_count = 0

    async def _drifting_policy_adapter(_: str) -> list[RetrievalHit]:
        nonlocal adapter_call_count
        adapter_call_count += 1
        if adapter_call_count == 1:
            title = "Wrong Policy Title"
            snippet = "The wrong title should not be exported."
        else:
            title = "Climate Order 2026"
            snippet = "The Climate Order takes effect on May 1, 2026."
        return [
            RetrievalHit(
                source_id="policy_official_registry",
                title=title,
                url="https://www.gov.cn/policy/climate-order-2026",
                snippet=snippet,
                credibility_tier="official_government",
                authority="State Council",
                jurisdiction="CN",
                publication_date="2026-04-01",
                effective_date="2026-05-01",
                version="2026-04 edition",
            )
        ]

    monkeypatch.setattr(api_entry, "classify_query", _policy_classification)
    monkeypatch.setattr(
        api_entry,
        "_default_adapter_registry",
        lambda: {"policy_official_registry": _drifting_policy_adapter},
    )
    api_entry.app.state.adapter_registry = {
        "policy_official_registry": _drifting_policy_adapter,
    }
    api_entry.app.state.model_client = _NeverCalledModelClient()
    cases = [BenchmarkCase(case_id="policy-01", query="latest climate order version")]

    try:
        with TestClient(api_entry.app) as client:
            response = client.post("/answer", json={"query": "latest climate order version"})
            response.raise_for_status()
        baseline_call_count = adapter_call_count
        ANSWER_CACHE.clear()
        adapter_call_count = 0

        export_judge_packets(
            app=api_entry.app,
            cases=cases,
            output_dir=tmp_path,
        )
    finally:
        ANSWER_CACHE.clear()
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    packet = json.loads(
        (tmp_path / "judge-packets" / "policy-01.json").read_text(encoding="utf-8")
    )
    assert adapter_call_count == baseline_call_count
    assert packet["retrieve"]["status"] == "success"
    assert packet["retrieve"]["canonical_evidence"]
    assert packet["retrieve"]["canonical_evidence"][0]["canonical_title"] == "Climate Order 2026"
    assert packet["answer"]["answer_status"] == "grounded_success"


def test_export_judge_packets_writes_minimal_case_packet(monkeypatch, tmp_path) -> None:
    import skill.api.entry as api_entry

    from skill.benchmark.judge_packets import export_judge_packets

    ANSWER_CACHE.clear()
    monkeypatch.setattr(api_entry, "classify_query", _policy_classification)
    monkeypatch.setattr(
        api_entry,
        "_default_adapter_registry",
        lambda: {"policy_official_registry": _policy_adapter},
    )
    api_entry.app.state.adapter_registry = {
        "policy_official_registry": _policy_adapter,
    }
    api_entry.app.state.model_client = _NeverCalledModelClient()
    cases = [BenchmarkCase(case_id="policy-01", query="latest climate order version")]

    try:
        index_payload = export_judge_packets(
            app=api_entry.app,
            cases=cases,
            output_dir=tmp_path,
        )
    finally:
        ANSWER_CACHE.clear()
        del api_entry.app.state.adapter_registry
        del api_entry.app.state.model_client

    assert index_payload["total_cases"] == 1
    packet_path = tmp_path / "judge-packets" / "policy-01.json"
    assert packet_path.exists()

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert set(packet) == {
        "case_id",
        "query",
        "retrieve",
        "answer",
        "runtime",
    }
    assert packet["case_id"] == "policy-01"
    assert packet["query"] == "latest climate order version"
    assert packet["retrieve"]["status"] == "success"
    assert packet["retrieve"]["canonical_evidence"]
    assert packet["answer"]["answer_status"] == "grounded_success"
    assert packet["answer"]["key_points"]
    assert packet["answer"]["sources"]
    assert packet["runtime"]["elapsed_ms"] >= 0
    assert isinstance(packet["runtime"]["retrieval_trace"], list)


def test_export_judge_packets_cli_writes_index_and_packets(monkeypatch, tmp_path) -> None:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "export_judge_packets.py"
    spec = importlib.util.spec_from_file_location("export_judge_packets_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    manifest_path = tmp_path / "cases.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "policy-01",
                    "query": "latest climate order version",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    def _fake_export_judge_packets(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        packet_dir = output_dir / "judge-packets"
        packet_dir.mkdir(parents=True, exist_ok=True)
        (packet_dir / "policy-01.json").write_text("{}", encoding="utf-8")
        index_payload = {
            "total_cases": 1,
            "packet_paths": ["judge-packets/policy-01.json"],
        }
        (output_dir / "judge-packets-index.json").write_text(
            json.dumps(index_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return index_payload

    monkeypatch.setattr(module, "export_judge_packets", _fake_export_judge_packets)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_judge_packets.py",
            "--cases",
            str(manifest_path),
            "--output-dir",
            str(tmp_path),
        ],
    )

    module.main()

    assert observed["cases_path"] == manifest_path
    assert observed["output_dir"] == tmp_path
    assert (tmp_path / "judge-packets-index.json").exists()
    assert (tmp_path / "judge-packets" / "policy-01.json").exists()
