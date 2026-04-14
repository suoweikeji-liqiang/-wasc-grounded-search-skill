"""Shared async HTTP helpers for live retrieval."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping

import httpx

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _trust_env() -> bool:
    raw = (os.getenv("WASC_LIVE_HTTP_TRUST_ENV") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def fetch_text(
    *,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> str:
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    timeout_config = httpx.Timeout(timeout)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_config,
            trust_env=_trust_env(),
        ) as client:
            response = await client.get(url, params=params, headers=merged_headers)
            response.raise_for_status()
            return response.text


async def fetch_json(
    *,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> object:
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    timeout_config = httpx.Timeout(timeout)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_config,
            trust_env=_trust_env(),
        ) as client:
            response = await client.get(url, params=params, headers=merged_headers)
            response.raise_for_status()
            return response.json()
