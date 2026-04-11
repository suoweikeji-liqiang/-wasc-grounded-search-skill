"""Deterministic fallback transition helpers for retrieval runtime."""

from __future__ import annotations

import asyncio

from skill.config.retrieval import SOURCE_BACKUP_CHAIN
from skill.retrieval.models import RetrievalFailureReason


def map_exception_to_failure_reason(exc: BaseException) -> RetrievalFailureReason:
    """Map adapter/runtime exceptions to stable retrieval failure reasons."""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return "rate_limited"

    return "adapter_error"


def next_source_for_failure(
    source_id: str,
    failure_reason: RetrievalFailureReason,
) -> str | None:
    """Return deterministic fallback source for a source+failure combination."""
    transitions = SOURCE_BACKUP_CHAIN.get(source_id)
    if transitions is None:
        return None
    return transitions.get(failure_reason)
