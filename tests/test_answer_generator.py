"""Phase 4 prompt-building and generator regressions."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from skill.evidence.models import CanonicalEvidence, EvidenceSlice
from skill.evidence.normalize import build_raw_record
from skill.retrieval.models import RetrievalHit

from skill.synthesis.generator import (
    MiniMaxTextClient,
    ModelBackendError,
    generate_answer_draft,
)
from skill.synthesis.prompt import build_grounded_answer_prompt


class _FakeModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.observed_prompt: str | None = None

    def generate_text(self, prompt: str) -> str:
        self.observed_prompt = prompt
        return json.dumps(self.payload)


def _policy_canonical() -> CanonicalEvidence:
    raw_record = build_raw_record(
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
        ),
        route_role="primary",
    )
    return CanonicalEvidence(
        evidence_id="policy-1",
        domain="policy",
        canonical_title="Climate Order 2026",
        canonical_url="https://www.gov.cn/policy/climate-order-2026",
        raw_records=(raw_record,),
        retained_slices=(
            EvidenceSlice(
                text="The Climate Order takes effect on May 1, 2026.",
                source_record_id="policy-1-slice-1",
                source_span="snippet",
                score=1.0,
                token_estimate=8,
            ),
        ),
        authority="State Council",
        jurisdiction="CN",
        jurisdiction_status="observed",
        publication_date="2026-04-01",
        effective_date="2026-05-01",
        version="2026-04 edition",
        version_status="observed",
        route_role="primary",
    )


def _academic_canonical() -> CanonicalEvidence:
    raw_record = build_raw_record(
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Grounded Search Evidence Packing",
            url="https://doi.org/10.1000/evidence-packing",
            snippet="The paper proposes evidence packing with bounded context windows.",
            credibility_tier="peer_reviewed",
            doi="10.1000/evidence-packing",
            arxiv_id="2604.12345",
            first_author="Lin",
            year=2026,
            evidence_level="peer_reviewed",
        ),
        route_role="supplemental",
    )
    return CanonicalEvidence(
        evidence_id="paper-1",
        domain="academic",
        canonical_title="Grounded Search Evidence Packing",
        canonical_url="https://doi.org/10.1000/evidence-packing",
        raw_records=(raw_record,),
        retained_slices=(
            EvidenceSlice(
                text="The paper proposes evidence packing with bounded context windows.",
                source_record_id="paper-1-slice-1",
                source_span="snippet",
                score=0.9,
                token_estimate=9,
            ),
        ),
        evidence_level="peer_reviewed",
        canonical_match_confidence="heuristic",
        doi="10.1000/evidence-packing",
        arxiv_id="2604.12345",
        first_author="Lin",
        year=2026,
        route_role="supplemental",
    )


def test_build_grounded_answer_prompt_serializes_evidence_ids_and_retained_slices() -> None:
    prompt = build_grounded_answer_prompt(
        query="latest climate order version",
        canonical_evidence=(_policy_canonical(), _academic_canonical()),
        evidence_clipped=True,
        evidence_pruned=False,
        retrieval_gaps=("Only one peer-reviewed source was retained.",),
    )

    assert "latest climate order version" in prompt
    assert "policy-1" in prompt
    assert "paper-1" in prompt
    assert "policy-1-slice-1" in prompt
    assert "paper-1-slice-1" in prompt
    assert "evidence_clipped: true" in prompt
    assert "Only one peer-reviewed source was retained." in prompt


def test_generate_answer_draft_parses_structured_json_from_fake_client() -> None:
    model_client = _FakeModelClient(
        {
            "conclusion": "The Climate Order takes effect on May 1, 2026.",
            "key_points": [
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
                    ]
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "Climate Order 2026",
                    "url": "https://www.gov.cn/policy/climate-order-2026"
                }
            ],
            "uncertainty_notes": []
        }
    )

    draft = generate_answer_draft("prompt text", model_client=model_client)

    assert model_client.observed_prompt == "prompt text"
    assert draft.conclusion == "The Climate Order takes effect on May 1, 2026."
    assert draft.key_points[0].citations[0].source_record_id == "policy-1-slice-1"
    assert draft.sources[0].evidence_id == "policy-1"


def test_generate_answer_draft_rejects_missing_quote_text() -> None:
    model_client = _FakeModelClient(
        {
            "conclusion": "Incomplete citation payload",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "Unsupported statement",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026"
                        }
                    ]
                }
            ],
            "sources": [],
            "uncertainty_notes": []
        }
    )

    with pytest.raises(ValueError, match="quote_text"):
        generate_answer_draft("prompt text", model_client=model_client)


def test_generate_answer_draft_rejects_non_object_citation_items() -> None:
    model_client = _FakeModelClient(
        {
            "conclusion": "Bad citation item",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "Unsupported statement",
                    "citations": ["not-a-citation-object"],
                }
            ],
            "sources": [],
            "uncertainty_notes": [],
        }
    )

    with pytest.raises(ValueError, match="citation items must be JSON objects"):
        generate_answer_draft("prompt text", model_client=model_client)


def test_generate_answer_draft_coerces_nullable_and_string_list_fields() -> None:
    model_client = _FakeModelClient(
        {
            "conclusion": "Grounded answer with light drift.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
                        }
                    ],
                }
            ],
            "sources": [
                {
                    "evidence_id": "policy-1",
                    "title": "Climate Order 2026",
                    "url": "https://www.gov.cn/policy/climate-order-2026",
                }
            ],
            "uncertainty_notes": "Evidence relevance is limited.",
            "gaps": None,
        }
    )

    draft = generate_answer_draft("prompt text", model_client=model_client)

    assert draft.uncertainty_notes == ["Evidence relevance is limited."]
    assert draft.gaps == []


def test_generate_answer_draft_extracts_json_from_wrapped_text() -> None:
    class _WrappedTextClient:
        def generate_text(self, prompt: str) -> str:
            return (
                "Here is the structured answer:\n"
                "```json\n"
                '{"conclusion":"ok","key_points":[],"sources":[],"uncertainty_notes":[]}\n'
                "```"
            )

    draft = generate_answer_draft("prompt text", model_client=_WrappedTextClient())

    assert draft.conclusion == "ok"
    assert draft.key_points == []
    assert draft.sources == []
    assert draft.uncertainty_notes == []


def test_generate_answer_draft_ignores_malformed_source_items() -> None:
    model_client = _FakeModelClient(
        {
            "conclusion": "Grounded answer with malformed sources.",
            "key_points": [
                {
                    "key_point_id": "kp-1",
                    "statement": "The Climate Order takes effect on May 1, 2026.",
                    "citations": [
                        {
                            "evidence_id": "policy-1",
                            "source_record_id": "policy-1-slice-1",
                            "source_url": "https://www.gov.cn/policy/climate-order-2026",
                            "quote_text": "The Climate Order takes effect on May 1, 2026.",
                        }
                    ],
                }
            ],
            "sources": [
                {"evidence_id": "policy-1"},
                "not-an-object",
            ],
            "uncertainty_notes": [],
        }
    )

    draft = generate_answer_draft("prompt text", model_client=model_client)

    assert draft.sources == []


def test_minimax_text_client_defaults_to_competition_model() -> None:
    client = MiniMaxTextClient(api_key="test-key")
    assert client.model == "MiniMax-M2.7"


def test_minimax_text_client_strips_wrapping_quotes_from_api_key(monkeypatch) -> None:
    import skill.synthesis.generator as generator_module

    observed: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "{\"conclusion\":\"ok\",\"key_points\":[],\"sources\":[],\"uncertainty_notes\":[]}"
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def _fake_urlopen(request, timeout: float):
        observed["authorization"] = request.get_header("Authorization")
        return _FakeResponse()

    monkeypatch.setattr(generator_module, "urlopen", _fake_urlopen)

    client = MiniMaxTextClient(api_key='"test-key"')
    client.generate_text("prompt text")

    assert observed["authorization"] == "Bearer test-key"


def test_minimax_text_client_calls_openai_compatible_api(monkeypatch) -> None:
    import skill.synthesis.generator as generator_module

    observed: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "{\"conclusion\":\"ok\",\"key_points\":[],\"sources\":[],\"uncertainty_notes\":[]}"
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def _fake_urlopen(request, timeout: float):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["authorization"] = request.get_header("Authorization")
        observed["content_type"] = request.get_header("Content-type")
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(generator_module, "urlopen", _fake_urlopen)

    client = MiniMaxTextClient(api_key="test-key")
    response_text = client.generate_text("prompt text")

    assert observed["url"] == "https://api.minimaxi.com/v1/chat/completions"
    assert observed["timeout"] == 120.0
    assert observed["authorization"] == "Bearer test-key"
    assert observed["content_type"] == "application/json"
    assert observed["payload"] == {
        "model": "MiniMax-M2.7",
        "messages": [
            {
                "role": "system",
                "content": "You are a grounded answer generator. Return valid JSON only.",
            },
            {"role": "user", "content": "prompt text"},
        ],
        "temperature": 0.1,
        "reasoning_split": True,
    }
    assert response_text == "{\"conclusion\":\"ok\",\"key_points\":[],\"sources\":[],\"uncertainty_notes\":[]}"


def test_minimax_text_client_normalizes_urlopen_timeout_to_timeout_error(
    monkeypatch,
) -> None:
    import skill.synthesis.generator as generator_module

    def _timeout_urlopen(request, timeout: float):
        raise URLError(TimeoutError("_ssl.c:989: The handshake operation timed out"))

    monkeypatch.setattr(generator_module, "urlopen", _timeout_urlopen)

    client = MiniMaxTextClient(api_key="test-key")

    with pytest.raises(TimeoutError, match="handshake operation timed out"):
        client.generate_text("prompt text")


def test_minimax_text_client_normalizes_http_error_to_model_backend_error(
    monkeypatch,
) -> None:
    import skill.synthesis.generator as generator_module

    def _http_error_urlopen(request, timeout: float):
        raise HTTPError(
            url=request.full_url,
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(generator_module, "urlopen", _http_error_urlopen)

    client = MiniMaxTextClient(api_key="test-key")

    with pytest.raises(ModelBackendError, match="status 500"):
        client.generate_text("prompt text")
