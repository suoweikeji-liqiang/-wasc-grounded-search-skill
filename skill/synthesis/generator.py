"""Structured grounded-answer generation helpers."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from skill.synthesis.models import ClaimCitation, KeyPoint, SourceReference, StructuredAnswerDraft

_SYSTEM_PROMPT = "You are a grounded answer generator. Return valid JSON only."


class ModelBackendError(RuntimeError):
    """Raised when the upstream generation backend fails before returning content."""


def _normalize_secret(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1].strip()
    return normalized


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise ValueError("Generator output was empty")

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()

    try:
        json.loads(text)
        return text
    except JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Generator output did not contain a JSON object")
    candidate = text[start : end + 1]
    json.loads(candidate)
    return candidate


def _coerce_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"{field_name} must be a list")


class ModelClient(Protocol):
    """Protocol for text-generation backends."""

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        """Generate raw text for the provided prompt."""


@dataclass(frozen=True)
class MiniMaxTextClient:
    """Thin MiniMax-compatible client boundary."""

    api_key: str
    model: str = "MiniMax-M2.7"
    base_url: str = "https://api.minimaxi.com/v1"
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_key", _normalize_secret(self.api_key))

    def generate_text(
        self, prompt: str, timeout_seconds: float | None = None
    ) -> str:
        if not self.api_key.strip():
            raise ValueError("MiniMaxTextClient requires a non-empty api_key")

        request_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "reasoning_split": True,
        }
        request = Request(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelBackendError(
                f"MiniMax request failed with status {exc.code}"
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(str(exc.reason)) from exc
            raise ModelBackendError(
                f"MiniMax request failed: {exc.reason}"
            ) from exc

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("MiniMax response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("MiniMax response choice must be an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("MiniMax response missing message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("MiniMax response missing content")
        return content


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
    citations: list[ClaimCitation] = []
    for item in citations_payload:
        if not isinstance(item, dict):
            raise ValueError("citation items must be JSON objects")
        citations.append(_parse_citation(item))
    return KeyPoint(
        key_point_id=str(_require_field(payload, "key_point_id")),
        statement=str(_require_field(payload, "statement")),
        citations=citations,
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
    timeout_seconds: float | None = None,
) -> StructuredAnswerDraft:
    """Generate and strictly parse a structured answer draft."""
    if timeout_seconds is None:
        raw_text = model_client.generate_text(prompt)
    else:
        try:
            raw_text = model_client.generate_text(
                prompt,
                timeout_seconds=timeout_seconds,
            )
        except TypeError as exc:
            if "timeout_seconds" not in str(exc):
                raise
            raw_text = model_client.generate_text(prompt)
    payload = json.loads(_extract_json_object(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Generator output must be a JSON object")

    key_points_payload = _require_field(payload, "key_points")
    sources_payload = _require_field(payload, "sources")
    uncertainty_payload = _coerce_string_list(
        _require_field(payload, "uncertainty_notes"),
        field_name="uncertainty_notes",
    )
    gaps_payload = _coerce_string_list(payload.get("gaps", []), field_name="gaps")

    if not isinstance(key_points_payload, list):
        raise ValueError("key_points must be a list")
    if not isinstance(sources_payload, list):
        raise ValueError("sources must be a list")
    key_points: list[KeyPoint] = []
    for item in key_points_payload:
        if not isinstance(item, dict):
            raise ValueError("key_points items must be JSON objects")
        key_points.append(_parse_key_point(item))

    sources: list[SourceReference] = []
    for item in sources_payload:
        if not isinstance(item, dict):
            continue
        try:
            sources.append(_parse_source(item))
        except ValueError:
            continue

    return StructuredAnswerDraft(
        conclusion=str(_require_field(payload, "conclusion")),
        key_points=key_points,
        sources=sources,
        uncertainty_notes=uncertainty_payload,
        gaps=gaps_payload,
    )
