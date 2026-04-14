"""Helpers for official-policy live retrieval."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


OFFICIAL_POLICY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "gov.cn",
        "www.gov.cn",
        "cac.gov.cn",
        "www.cac.gov.cn",
        "mee.gov.cn",
        "www.mee.gov.cn",
        "mofcom.gov.cn",
        "www.mofcom.gov.cn",
        "samr.gov.cn",
        "www.samr.gov.cn",
        "eur-lex.europa.eu",
        "taxation-customs.ec.europa.eu",
        "bis.gov",
        "www.bis.gov",
    }
)

_DOMAIN_METADATA: dict[str, tuple[str, str]] = {
    "gov.cn": ("State Council", "CN"),
    "www.gov.cn": ("State Council", "CN"),
    "cac.gov.cn": ("Cyberspace Administration of China", "CN"),
    "www.cac.gov.cn": ("Cyberspace Administration of China", "CN"),
    "mee.gov.cn": ("Ministry of Ecology and Environment", "CN"),
    "www.mee.gov.cn": ("Ministry of Ecology and Environment", "CN"),
    "mofcom.gov.cn": ("Ministry of Commerce", "CN"),
    "www.mofcom.gov.cn": ("Ministry of Commerce", "CN"),
    "samr.gov.cn": ("State Administration for Market Regulation", "CN"),
    "www.samr.gov.cn": ("State Administration for Market Regulation", "CN"),
    "eur-lex.europa.eu": ("European Union", "EU"),
    "taxation-customs.ec.europa.eu": ("European Commission", "EU"),
    "bis.gov": ("U.S. Department of Commerce", "US"),
    "www.bis.gov": ("U.S. Department of Commerce", "US"),
}

_ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
_CHINESE_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_AUTHORITY_RE = re.compile(r"(?:Authority|发布机关|发布单位)[:：]\s*(.+)")
_PUBLICATION_RE = re.compile(r"(?:Publication date|发布日期|发布时间)[:：]\s*([^\n]+)")
_EFFECTIVE_RE = re.compile(r"(?:Effective date|生效日期|施行日期)[:：]\s*([^\n]+)")
_VERSION_RE = re.compile(r"(?:Version|版本)[:：]\s*([^\n]+)")


def is_official_policy_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in OFFICIAL_POLICY_ALLOWLIST


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    iso_match = _ISO_DATE_RE.search(value)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"
    cn_match = _CHINESE_DATE_RE.search(value)
    if cn_match:
        year, month, day = cn_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def policy_domain_metadata(url: str) -> tuple[str | None, str | None]:
    host = (urlsplit(url).hostname or "").lower()
    authority, jurisdiction = _DOMAIN_METADATA.get(host, (None, None))
    return authority, jurisdiction


def extract_policy_metadata(
    *,
    url: str,
    page_text: str,
) -> dict[str, str | None]:
    default_authority, jurisdiction = policy_domain_metadata(url)
    authority_match = _AUTHORITY_RE.search(page_text)
    publication_match = _PUBLICATION_RE.search(page_text)
    effective_match = _EFFECTIVE_RE.search(page_text)
    version_match = _VERSION_RE.search(page_text)

    publication_date = _normalize_date(publication_match.group(1) if publication_match else None)
    effective_date = _normalize_date(effective_match.group(1) if effective_match else None)

    if publication_date is None or effective_date is None:
        observed_dates = [_normalize_date(match.group(0)) for match in _ISO_DATE_RE.finditer(page_text)]
        observed_dates.extend(
            _normalize_date(match.group(0))
            for match in _CHINESE_DATE_RE.finditer(page_text)
        )
        normalized_dates = [date for date in observed_dates if date]
        if publication_date is None and normalized_dates:
            publication_date = normalized_dates[0]
        if effective_date is None and len(normalized_dates) > 1:
            effective_date = normalized_dates[1]

    return {
        "authority": authority_match.group(1).strip() if authority_match else default_authority,
        "jurisdiction": jurisdiction,
        "publication_date": publication_date,
        "effective_date": effective_date,
        "version": version_match.group(1).strip() if version_match else None,
    }


def preferred_policy_domains(query: str, *, fallback: bool) -> tuple[str, ...]:
    normalized = query.lower()
    if "ai act" in normalized or "eu" in normalized or "cbam" in normalized:
        primary = ("eur-lex.europa.eu", "taxation-customs.ec.europa.eu")
    elif "export control" in normalized or "bis" in normalized or "u.s." in normalized or "us " in normalized:
        primary = ("bis.gov",)
    else:
        primary = ("gov.cn", "cac.gov.cn", "mee.gov.cn", "mofcom.gov.cn")

    if fallback:
        return primary + ("samr.gov.cn",)
    return primary
