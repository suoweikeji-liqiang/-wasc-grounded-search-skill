"""Parsers for live academic metadata sources."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _safe_str(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def parse_semantic_scholar_response(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    records: list[dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = _safe_str(item.get("title"))
        if title is None:
            continue
        abstract = _safe_str(item.get("abstract")) or ""
        url = _safe_str(item.get("url"))
        external_ids = item.get("externalIds")
        doi = None
        arxiv_id = None
        if isinstance(external_ids, dict):
            doi = _safe_str(external_ids.get("DOI"))
            arxiv_id = _safe_str(external_ids.get("ArXiv"))
        authors = item.get("authors")
        first_author = None
        if isinstance(authors, list) and authors:
            first = authors[0]
            if isinstance(first, dict):
                first_author = _safe_str(first.get("name"))
        year_value = item.get("year")
        year = int(year_value) if isinstance(year_value, int) else None
        evidence_level = "peer_reviewed" if doi else "metadata_only"
        records.append(
            {
                "title": title,
                "url": url or "",
                "snippet": abstract or title,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "first_author": first_author,
                "year": year,
                "evidence_level": evidence_level,
            }
        )
    return records


def parse_arxiv_feed(xml_text: str) -> list[dict[str, object]]:
    root = ET.fromstring(xml_text)
    records: list[dict[str, object]] = []

    for entry in root.findall("atom:entry", _ATOM_NS):
        title = (entry.findtext("atom:title", default="", namespaces=_ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=_ATOM_NS) or "").strip()
        url = (entry.findtext("atom:id", default="", namespaces=_ATOM_NS) or "").strip()
        if not title or not url:
            continue
        author = entry.find("atom:author/atom:name", _ATOM_NS)
        published = (entry.findtext("atom:published", default="", namespaces=_ATOM_NS) or "").strip()
        year = None
        if len(published) >= 4 and published[:4].isdigit():
            year = int(published[:4])
        path = urlsplit(url).path.rstrip("/")
        arxiv_id = path.split("/")[-1] if path else None
        records.append(
            {
                "title": title,
                "url": url,
                "snippet": summary or title,
                "arxiv_id": arxiv_id,
                "first_author": author.text.strip() if author is not None and author.text else None,
                "year": year,
                "evidence_level": "preprint",
            }
        )
    return records
