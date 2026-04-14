"""Official gov.cn policy registry search client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.policy import parse_gov_policy_search_response

_SEARCH_ENDPOINT = "https://sousuo.www.gov.cn/search-gov/data"
_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)


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

    records: list[dict[str, object]] = []
    for searchfield in ("title", "title:content:summary"):
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
            timeout=4.0,
        )
        records = parse_gov_policy_search_response(payload)
        if records:
            break
    clipped = records[: max(1, max_results)]
    _CACHE.set(
        key,
        clipped,
        ttl_seconds=config.search_cache_ttl_seconds,
    )
    return clipped
