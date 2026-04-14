"""Helpers for extracting bounded content from fetched HTML pages."""

from __future__ import annotations

from bs4 import BeautifulSoup


def extract_page_content(html: str, *, max_chars: int = 4000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    parts: list[str] = []
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        parts.append(title)

    main = soup.find("main") or soup.body or soup
    text = main.get_text(" ", strip=True)
    if text:
        parts.append(text)

    content = " ".join(part for part in parts if part).strip()
    if not content:
        return ""
    return content[:max_chars]
