"""Official gov.cn policy registry search client."""

from __future__ import annotations

import asyncio

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.policy import parse_gov_policy_search_response

_SEARCH_ENDPOINT = "https://sousuo.www.gov.cn/search-gov/data"
_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_SEARCH_FIELDS: tuple[str, str] = ("title", "title:content:summary")
_REQUEST_TIMEOUT_SECONDS = 0.8


def _cache_key(query: str, *, max_results: int) -> str:
    return f"{query.strip().lower()}|{max(1, max_results)}"


def _search_params(
    query: str,
    *,
    max_results: int,
    searchfield: str,
) -> dict[str, str]:
    return {
        "t": "zhengcelibrary",
        "q": query,
        "timetype": "",
        "mintime": "",
        "maxtime": "",
        "sort": "score",
        "sortType": "1",
        "searchfield": searchfield,
        "pcodeJiguan": "",
        "childtype": "",
        "subchildtype": "",
        "tsbq": "",
        "pubtimeyear": "",
        "puborg": "",
        "pcodeYear": "",
        "pcodeNum": "",
        "filetype": "",
        "p": "0",
        "n": str(max(1, max_results)),
        "inpro": "",
        "bmfl": "",
        "dup": "",
        "orpro": "",
        "type": "gwyzcwjk",
    }


async def _search_field(
    *,
    query: str,
    max_results: int,
    searchfield: str,
) -> list[dict[str, object]]:
    payload = await http_client.fetch_json(
        url=_SEARCH_ENDPOINT,
        params=_search_params(
            query,
            max_results=max_results,
            searchfield=searchfield,
        ),
        headers={
            "Referer": "https://sousuo.www.gov.cn/zcwjk/",
        },
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    return parse_gov_policy_search_response(payload)


def _detach_task(task: asyncio.Task[object]) -> None:
    def _consume_result(done_task: asyncio.Task[object]) -> None:
        try:
            done_task.result()
        except BaseException:
            return

    task.add_done_callback(_consume_result)


def _cancel_if_pending(task: asyncio.Task[list[dict[str, object]]] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    _detach_task(task)


async def search_policy_registry(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    title_task = asyncio.create_task(
        _search_field(
            query=query,
            max_results=max_results,
            searchfield=_SEARCH_FIELDS[0],
        )
    )
    broader_task = asyncio.create_task(
        _search_field(
            query=query,
            max_results=max_results,
            searchfield=_SEARCH_FIELDS[1],
        )
    )

    try:
        try:
            title_records = await title_task
        except Exception:
            title_records = []

        if title_records:
            _cancel_if_pending(broader_task)
            clipped = title_records[: max(1, max_results)]
            _CACHE.set(
                key,
                clipped,
                ttl_seconds=config.search_cache_ttl_seconds,
            )
            return clipped

        try:
            broader_records = await broader_task
        except Exception:
            broader_records = []
    except asyncio.CancelledError:
        _cancel_if_pending(title_task)
        _cancel_if_pending(broader_task)
        raise

    records = broader_records
    clipped = records[: max(1, max_results)]
    _CACHE.set(
        key,
        clipped,
        ttl_seconds=config.search_cache_ttl_seconds,
    )
    return clipped
