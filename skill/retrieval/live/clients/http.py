"""Shared async HTTP helpers for live retrieval."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


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
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
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
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url, params=params, headers=merged_headers)
        response.raise_for_status()
        return response.json()
