"""Minimal SERP parsers for live search discovery."""

from __future__ import annotations

import base64
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _decode_bing_redirect(url: str) -> str:
    parts = urlsplit(url)
    if "bing.com" not in parts.netloc or not parts.path.startswith("/ck/"):
        return url
    params = parse_qs(parts.query)
    encoded = params.get("u", [None])[0]
    if not encoded:
        return url
    token = unquote(encoded).replace("\n", "").replace("\r", "")
    if token.startswith("a1"):
        token = token[2:]
    padding = "=" * ((4 - len(token) % 4) % 4)
    try:
        decoded = base64.b64decode(token + padding).decode("utf-8")
    except Exception:
        return url
    return decoded or url


def parse_duckduckgo_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for container in soup.select("div.result"):
        link = container.select_one("a.result__a")
        snippet = container.select_one(".result__snippet")
        if link is None or not link.get("href"):
            continue
        results.append(
            {
                "title": _clean_text(link.get_text(" ", strip=True)),
                "url": str(link["href"]),
                "snippet": _clean_text(snippet.get_text(" ", strip=True)) if snippet else "",
            }
        )
    return results


def parse_bing_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for container in soup.select("li.b_algo"):
        link = container.select_one("h2 a")
        snippet = container.select_one(".b_caption p")
        if link is None or not link.get("href"):
            continue
        results.append(
            {
                "title": _clean_text(link.get_text(" ", strip=True)),
                "url": _decode_bing_redirect(str(link["href"])),
                "snippet": _clean_text(snippet.get_text(" ", strip=True)) if snippet else "",
            }
        )
    return results


def parse_google_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for container in soup.select("div.g"):
        link = container.select_one("a")
        snippet = container.select_one(".VwiC3b")
        if link is None or not link.get("href"):
            continue
        results.append(
            {
                "title": _clean_text(link.get_text(" ", strip=True)),
                "url": str(link["href"]),
                "snippet": _clean_text(snippet.get_text(" ", strip=True)) if snippet else "",
            }
        )
    return results
