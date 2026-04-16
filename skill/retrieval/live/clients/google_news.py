"""Helpers for resolving Google News article redirects to publisher URLs."""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import quote
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from skill.retrieval.live.clients import http as http_client

_ARTICLE_PATH_MARKERS: frozenset[str] = frozenset({"articles", "read"})
_ARTICLE_ATTR_PATTERN = re.compile(
    r'data-n-a-ts="(?P<timestamp>[^"]+)".*?data-n-a-sg="(?P<signature>[^"]+)"'
    r'|data-n-a-sg="(?P<signature_alt>[^"]+)".*?data-n-a-ts="(?P<timestamp_alt>[^"]+)"',
    re.DOTALL,
)
_GARTURLRES_ESCAPED_RE = re.compile(r'garturlres\\",\\"(?P<url>https?://[^\\"]+)')
_GARTURLRES_PLAIN_RE = re.compile(r'\["garturlres","(?P<url>https?://[^"]+)')
_LEGACY_PREFIX = b"\x08\x13\x22"
_LEGACY_SUFFIX = b"\xd2\x01\x00"
_ARTICLE_PAGE_TIMEOUT_SECONDS = 2.0
_BATCHEXECUTE_TIMEOUT_SECONDS = 3.0
_ARTICLE_PAGE_MAX_CHARS = 180_000
_BATCHEXECUTE_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Referrer": "https://news.google.com/",
}


def _article_id_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    path_parts = [part for part in parts.path.split("/") if part]
    if parts.hostname != "news.google.com" or len(path_parts) < 2:
        return None
    if path_parts[-2] not in _ARTICLE_PATH_MARKERS:
        return None
    return path_parts[-1]


def _decode_legacy_article_id(article_id: str) -> str | None:
    padded = article_id + "=" * ((4 - len(article_id) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded)
    except Exception:
        return None

    if decoded.startswith(_LEGACY_PREFIX):
        decoded = decoded[len(_LEGACY_PREFIX):]
    if decoded.endswith(_LEGACY_SUFFIX):
        decoded = decoded[: -len(_LEGACY_SUFFIX)]
    if not decoded:
        return None

    length = decoded[0]
    offset = 1
    if length >= 0x80:
        if len(decoded) < 2:
            return None
        offset = 2
        length = ((length & 0x7F) << 8) | decoded[1]
    if len(decoded) < offset + length:
        return None

    candidate = decoded[offset : offset + length].decode("utf-8", errors="ignore").strip()
    if candidate.startswith(("http://", "https://")):
        return candidate
    return None


def _extract_decoder_inputs(article_page_html: str) -> tuple[str, str] | None:
    match = _ARTICLE_ATTR_PATTERN.search(article_page_html)
    if match is None:
        soup = BeautifulSoup(article_page_html, "html.parser")
        candidate_node = soup.select_one("c-wiz > div[jscontroller]")
        if candidate_node is None:
            candidate_node = soup.find(attrs={"data-n-a-sg": True, "data-n-a-ts": True})
        if candidate_node is None:
            return None
        timestamp = str(candidate_node.get("data-n-a-ts") or "").strip()
        signature = str(candidate_node.get("data-n-a-sg") or "").strip()
        if not timestamp or not signature:
            return None
        return timestamp, signature
    timestamp = match.group("timestamp") or match.group("timestamp_alt")
    signature = match.group("signature") or match.group("signature_alt")
    if not timestamp or not signature:
        return None
    return timestamp, signature


def _article_page_urls(article_id: str) -> tuple[str, ...]:
    return (
        f"https://news.google.com/articles/{article_id}",
        f"https://news.google.com/rss/articles/{article_id}",
    )


def _decode_batchexecute_response(response_text: str) -> str | None:
    for pattern in (_GARTURLRES_ESCAPED_RE, _GARTURLRES_PLAIN_RE):
        match = pattern.search(response_text)
        if match is not None:
            return match.group("url")

    payload_blocks = response_text.split("\n\n", 1)
    if len(payload_blocks) < 2:
        return None
    try:
        parsed = json.loads(payload_blocks[1])
    except json.JSONDecodeError:
        return None

    for item in parsed:
        if not isinstance(item, list) or len(item) < 3:
            continue
        inner = item[2]
        if not isinstance(inner, str):
            continue
        try:
            decoded_inner = json.loads(inner)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(decoded_inner, list)
            and len(decoded_inner) >= 2
            and decoded_inner[0] == "garturlres"
            and isinstance(decoded_inner[1], str)
        ):
            return decoded_inner[1]
    return None


def _batchexecute_request_payload(
    *,
    article_id: str,
    timestamp: str,
    signature: str,
) -> str:
    payload = [
        "Fbv4je",
        (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,'
            'null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
            f'"{article_id}",{timestamp},"{signature}"]'
        ),
    ]
    return "f.req=" + quote(json.dumps([[payload]], separators=(",", ":")))


async def resolve_google_news_article_url(url: str) -> str | None:
    article_id = _article_id_from_url(url)
    if article_id is None:
        return None

    legacy_url = _decode_legacy_article_id(article_id)
    if legacy_url is not None and not legacy_url.startswith("AU_yqL"):
        return legacy_url

    decoder_inputs: tuple[str, str] | None = None
    for article_page_url in _article_page_urls(article_id):
        try:
            article_page_html = await http_client.fetch_text_limited(
                url=article_page_url,
                timeout=_ARTICLE_PAGE_TIMEOUT_SECONDS,
                max_chars=_ARTICLE_PAGE_MAX_CHARS,
                cache_scope="page",
                cache_key=article_page_url,
            )
        except Exception:
            continue
        decoder_inputs = _extract_decoder_inputs(article_page_html)
        if decoder_inputs is not None:
            break
    if decoder_inputs is None:
        return None
    timestamp, signature = decoder_inputs

    try:
        response_text = await http_client.post_text(
            url="https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
            data=_batchexecute_request_payload(
                article_id=article_id,
                timestamp=timestamp,
                signature=signature,
            ),
            headers=_BATCHEXECUTE_HEADERS,
            timeout=_BATCHEXECUTE_TIMEOUT_SECONDS,
        )
    except Exception:
        return None

    decoded_url = _decode_batchexecute_response(response_text)
    if decoded_url and not decoded_url.startswith("https://news.google.com/"):
        return decoded_url
    return None
