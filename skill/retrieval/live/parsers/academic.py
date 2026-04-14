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


def _safe_int(value: object | None) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _first_author(authors: object) -> str | None:
    if not isinstance(authors, list) or not authors:
        return None
    first = authors[0]
    if not isinstance(first, dict):
        return None
    return _safe_str(first.get("name"))


def _extract_arxiv_id(url: str | None) -> str | None:
    if not url:
        return None
    path = urlsplit(url).path.rstrip("/")
    if "/abs/" not in path:
        return None
    candidate = path.split("/")[-1]
    if candidate:
        return candidate.removesuffix(".pdf")
    return None


def _asta_record(item: dict[str, object]) -> dict[str, object] | None:
    title = _safe_str(item.get("title"))
    url = _safe_str(item.get("url"))
    if title is None or url is None:
        return None

    abstract = _safe_str(item.get("abstract"))
    tldr = item.get("tldr")
    tldr_text = None
    if isinstance(tldr, dict):
        tldr_text = _safe_str(tldr.get("text"))
    snippet = abstract or tldr_text or title
    authors = item.get("authors")
    year = _safe_int(item.get("year"))
    venue = (_safe_str(item.get("venue")) or "").strip()
    external_ids = item.get("externalIds")
    doi = None
    arxiv_id = _extract_arxiv_id(url)
    if isinstance(external_ids, dict):
        doi = _safe_str(external_ids.get("DOI")) or _safe_str(external_ids.get("doi"))
        arxiv_id = (
            _safe_str(external_ids.get("ArXiv"))
            or _safe_str(external_ids.get("arXiv"))
            or arxiv_id
        )

    url_lower = url.lower()
    venue_lower = venue.lower()
    if doi:
        evidence_level = "peer_reviewed"
    elif arxiv_id or "arxiv" in url_lower or "arxiv" in venue_lower:
        evidence_level = "preprint"
    elif venue:
        evidence_level = "peer_reviewed"
    else:
        evidence_level = "metadata_only"

    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "first_author": _first_author(authors),
        "year": year,
        "evidence_level": evidence_level,
    }


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
        first_author = _first_author(authors)
        year = _safe_int(item.get("year"))
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


def parse_asta_search_result(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    structured = payload.get("structuredContent")
    if not isinstance(structured, dict):
        return []
    result = structured.get("result")
    if result is None:
        return []
    if isinstance(result, dict):
        parsed = _asta_record(result)
        return [parsed] if parsed is not None else []
    if not isinstance(result, list):
        return []

    records: list[dict[str, object]] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        parsed = _asta_record(item)
        if parsed is not None:
            records.append(parsed)
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


def _abstract_from_inverted_index(index: object) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    positioned_terms: list[tuple[int, str]] = []
    for term, positions in index.items():
        if not isinstance(term, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_terms.append((position, term))
    if not positioned_terms:
        return None
    ordered = [term for _, term in sorted(positioned_terms, key=lambda item: item[0])]
    return " ".join(ordered)


def parse_openalex_response(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    records: list[dict[str, object]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = _safe_str(item.get("display_name")) or _safe_str(item.get("title"))
        if title is None:
            continue
        doi = _safe_str(item.get("doi"))
        authorships = item.get("authorships")
        first_author = None
        if isinstance(authorships, list) and authorships:
            first_authorship = authorships[0]
            if isinstance(first_authorship, dict):
                author = first_authorship.get("author")
                if isinstance(author, dict):
                    first_author = _safe_str(author.get("display_name"))

        location_url = None
        for key in ("primary_location", "best_oa_location"):
            location = item.get(key)
            if not isinstance(location, dict):
                continue
            location_url = _safe_str(location.get("landing_page_url")) or _safe_str(
                location.get("pdf_url")
            )
            if location_url:
                break

        abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
        work_type = (_safe_str(item.get("type")) or "").lower()
        evidence_level = (
            "peer_reviewed"
            if doi or work_type in {"article", "journal-article", "review", "review-article"}
            else "metadata_only"
        )

        records.append(
            {
                "title": title,
                "url": doi or location_url or _safe_str(item.get("id")) or "",
                "snippet": abstract or title,
                "doi": doi.removeprefix("https://doi.org/") if doi else None,
                "first_author": first_author,
                "year": _safe_int(item.get("publication_year")),
                "evidence_level": evidence_level,
            }
        )
    return records


def parse_europe_pmc_response(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    result_list = payload.get("resultList")
    if not isinstance(result_list, dict):
        return []
    results = result_list.get("result")
    if not isinstance(results, list):
        return []

    records: list[dict[str, object]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = _safe_str(item.get("title"))
        if title is None:
            continue
        source = _safe_str(item.get("source")) or "MED"
        record_id = _safe_str(item.get("id")) or _safe_str(item.get("pmid"))
        doi = _safe_str(item.get("doi"))
        if doi:
            url = f"https://doi.org/{doi}"
        elif record_id:
            url = f"https://europepmc.org/article/{source}/{record_id}"
        else:
            continue

        author_string = _safe_str(item.get("authorString")) or ""
        first_author = author_string.split(",", 1)[0].strip() or None
        pub_type = (_safe_str(item.get("pubType")) or "").lower()
        evidence_level = "preprint" if source == "PPR" else "peer_reviewed"
        if "review" in pub_type and evidence_level != "preprint":
            evidence_level = "peer_reviewed"

        snippet_parts = [
            _safe_str(item.get("journalTitle")) or "",
            author_string,
            _safe_str(item.get("firstPublicationDate")) or "",
        ]
        snippet = " ".join(part for part in snippet_parts if part).strip() or title

        records.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "doi": doi,
                "first_author": first_author,
                "year": _safe_int(item.get("pubYear")),
                "evidence_level": evidence_level,
            }
        )
    return records
