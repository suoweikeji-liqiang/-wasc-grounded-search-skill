"""Shared async HTTP helpers for live retrieval."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import FileTTLCache, TTLCache

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

CacheScope = Literal["none", "search", "page", "academic"]

_MEMORY_CACHES: dict[CacheScope, TTLCache[object]] = {
    "none": TTLCache(max_entries=1),
    "search": TTLCache(max_entries=128),
    "page": TTLCache(max_entries=128),
    "academic": TTLCache(max_entries=128),
}
_DISK_CACHES: dict[tuple[CacheScope, str], FileTTLCache[object]] = {}


def _trust_env() -> bool:
    raw = (os.getenv("WASC_LIVE_HTTP_TRUST_ENV") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _config() -> LiveRetrievalConfig:
    return LiveRetrievalConfig.from_env()


def _ttl_seconds(scope: CacheScope, config: LiveRetrievalConfig) -> int:
    if scope == "search":
        return config.search_cache_ttl_seconds
    if scope == "page":
        return config.page_cache_ttl_seconds
    if scope == "academic":
        return config.academic_cache_ttl_seconds
    return 0


def _canonical_page_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _cache_key_from_request(
    *,
    method: str,
    url: str,
    params: Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    extra: Mapping[str, str] | None = None,
) -> str:
    normalized_params = tuple(
        sorted((str(key), str(value)) for key, value in (params or {}).items())
    )
    normalized_headers = tuple(
        sorted((str(key).lower(), str(value)) for key, value in (headers or {}).items())
    )
    normalized_extra = tuple(
        sorted((str(key), str(value)) for key, value in (extra or {}).items())
    )
    return repr(
        (
            method.upper(),
            url,
            normalized_params,
            normalized_headers,
            normalized_extra,
        )
    )


def _disk_cache(scope: CacheScope, *, config: LiveRetrievalConfig) -> FileTTLCache[object] | None:
    if scope == "none":
        return None
    root_dir = str(Path(config.cache_dir))
    cache_key = (scope, root_dir)
    cache = _DISK_CACHES.get(cache_key)
    if cache is None:
        cache = FileTTLCache(root_dir=Path(root_dir), namespace=scope)
        _DISK_CACHES[cache_key] = cache
    return cache


def _get_cached_value(
    *,
    scope: CacheScope,
    key: str,
    config: LiveRetrievalConfig,
) -> object | None:
    if scope == "none":
        return None
    memory_cache = _MEMORY_CACHES[scope]
    cached = memory_cache.get(key)
    if cached is not None:
        return cached
    disk_cache = _disk_cache(scope, config=config)
    if disk_cache is None:
        return None
    cached = disk_cache.get(key)
    if cached is not None:
        memory_cache.set(key, cached, ttl_seconds=_ttl_seconds(scope, config))
    return cached


def _set_cached_value(
    *,
    scope: CacheScope,
    key: str,
    value: object,
    config: LiveRetrievalConfig,
) -> None:
    ttl_seconds = _ttl_seconds(scope, config)
    if scope == "none" or ttl_seconds <= 0:
        return
    _MEMORY_CACHES[scope].set(key, value, ttl_seconds=ttl_seconds)
    disk_cache = _disk_cache(scope, config=config)
    if disk_cache is not None:
        disk_cache.set(key, value, ttl_seconds=ttl_seconds)


async def fetch_text(
    *,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    cache_scope: CacheScope = "none",
    cache_key: str | None = None,
) -> str:
    config = _config()
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    effective_cache_key = cache_key
    if cache_scope == "page" and effective_cache_key is None:
        effective_cache_key = f"page:{_canonical_page_url(url)}"
    if effective_cache_key is None:
        effective_cache_key = _cache_key_from_request(
            method="GET",
            url=url,
            params=params,
            headers=merged_headers,
        )
    cached = _get_cached_value(
        scope=cache_scope,
        key=effective_cache_key,
        config=config,
    )
    if isinstance(cached, str):
        return cached
    timeout_config = httpx.Timeout(timeout)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_config,
            trust_env=_trust_env(),
        ) as client:
            response = await client.get(url, params=params, headers=merged_headers)
            response.raise_for_status()
            text = response.text
            _set_cached_value(
                scope=cache_scope,
                key=effective_cache_key,
                value=text,
                config=config,
            )
            return text


async def fetch_text_limited(
    *,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    max_chars: int = 400_000,
    cache_scope: CacheScope = "none",
    cache_key: str | None = None,
) -> str:
    config = _config()
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    effective_cache_key = cache_key
    if cache_scope == "page" and effective_cache_key is None:
        effective_cache_key = f"page:{_canonical_page_url(url)}:chars={max(1, max_chars)}"
    if effective_cache_key is None:
        effective_cache_key = _cache_key_from_request(
            method="GET",
            url=url,
            params=params,
            headers=merged_headers,
            extra={"max_chars": str(max(1, max_chars))},
        )
    cached = _get_cached_value(
        scope=cache_scope,
        key=effective_cache_key,
        config=config,
    )
    if isinstance(cached, str):
        return cached
    timeout_config = httpx.Timeout(timeout)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_config,
            trust_env=_trust_env(),
        ) as client:
            async with client.stream(
                "GET",
                url,
                params=params,
                headers=merged_headers,
            ) as response:
                response.raise_for_status()
                parts: list[str] = []
                total_chars = 0
                async for chunk in response.aiter_text():
                    parts.append(chunk)
                    total_chars += len(chunk)
                    if total_chars >= max(1, max_chars):
                        break
                text = "".join(parts)
                _set_cached_value(
                    scope=cache_scope,
                    key=effective_cache_key,
                    value=text,
                    config=config,
                )
                return text


async def fetch_json(
    *,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    cache_scope: CacheScope = "none",
    cache_key: str | None = None,
) -> object:
    config = _config()
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    effective_cache_key = cache_key or _cache_key_from_request(
        method="GET",
        url=url,
        params=params,
        headers=merged_headers,
    )
    cached = _get_cached_value(
        scope=cache_scope,
        key=effective_cache_key,
        config=config,
    )
    if cached is not None:
        return cached
    timeout_config = httpx.Timeout(timeout)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_config,
            trust_env=_trust_env(),
        ) as client:
            response = await client.get(url, params=params, headers=merged_headers)
            response.raise_for_status()
            payload = response.json()
            _set_cached_value(
                scope=cache_scope,
                key=effective_cache_key,
                value=payload,
                config=config,
            )
            return payload


async def post_text(
    *,
    url: str,
    data: Mapping[str, str] | str | None = None,
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
            if isinstance(data, str):
                response = await client.post(url, content=data, headers=merged_headers)
            else:
                response = await client.post(
                    url,
                    data=cast(Mapping[str, str] | None, data),
                    headers=merged_headers,
                )
            response.raise_for_status()
            return response.text
