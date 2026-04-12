"""Structured grounded-answer generation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from skill.synthesis.models import ClaimCitation, KeyPoint, SourceReference, StructuredAnswerDraft


class ModelClient(Protocol):
    """Protocol for text-generation backends."""

    def generate_text(self, prompt: str) -> str:
        """Generate raw text for the provided prompt."""


@dataclass(frozen=True)
class MiniMaxTextClient:
    """Thin MiniMax-compatible client boundary."""

    api_key: str
    model: str = "MiniMax-M2.7"

    def generate_text(self, prompt: str) -> str:
        raise NotImplementedError("Live MiniMax calls are not wired in this offline test path.")


def _require_field(payload: dict[str, object], field_name: str) -> object:
    if field_name not in payload:
        raise ValueError(f"Missing required field: {field_name}")
    return payload[field_name]


def _parse_citation(payload: dict[str, object]) -> ClaimCitation:
    return ClaimCitation(
        evidence_id=str(_require_field(payload, "evidence_id")),
        source_record_id=str(_require_field(payload, "source_record_id")),
        source_url=str(_require_field(payload, "source_url")),
        quote_text=str(_require_field(payload, "quote_text")),
    )


def _parse_key_point(payload: dict[str, object]) -> KeyPoint:
    citations_payload = _require_field(payload, "citations")
    if not isinstance(citations_payload, list):
        raise ValueError("citations must be a list")
    return KeyPoint(
        key_point_id=str(_require_field(payload, "key_point_id")),
        statement=str(_require_field(payload, "statement")),
        citations=[
            _parse_citation(item)
            for item in citations_payload
            if isinstance(item, dict)
        ],
    )


def _parse_source(payload: dict[str, object]) -> SourceReference:
    return SourceReference(
        evidence_id=str(_require_field(payload, "evidence_id")),
        title=str(_require_field(payload, "title")),
        url=str(_require_field(payload, "url")),
    )


def generate_answer_draft(
    prompt: str,
    model_client: ModelClient,
) -> StructuredAnswerDraft:
    """Generate and strictly parse a structured answer draft."""
    raw_text = model_client.generate_text(prompt)
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("Generator output must be a JSON object")

    key_points_payload = _require_field(payload, "key_points")
    sources_payload = _require_field(payload, "sources")
    uncertainty_payload = _require_field(payload, "uncertainty_notes")
    gaps_payload = payload.get("gaps", [])

    if not isinstance(key_points_payload, list):
        raise ValueError("key_points must be a list")
    if not isinstance(sources_payload, list):
        raise ValueError("sources must be a list")
    if not isinstance(uncertainty_payload, list):
        raise ValueError("uncertainty_notes must be a list")
    if not isinstance(gaps_payload, list):
        raise ValueError("gaps must be a list")

    return StructuredAnswerDraft(
        conclusion=str(_require_field(payload, "conclusion")),
        key_points=[
            _parse_key_point(item)
            for item in key_points_payload
            if isinstance(item, dict)
        ],
        sources=[
            _parse_source(item)
            for item in sources_payload
            if isinstance(item, dict)
        ],
        uncertainty_notes=[str(item) for item in uncertainty_payload],
        gaps=[str(item) for item in gaps_payload],
    )
