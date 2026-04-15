"""Helpers for official-policy live retrieval."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from skill.orchestrator.normalize import normalize_query_text


OFFICIAL_POLICY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "gov.cn",
        "www.gov.cn",
        "flk.npc.gov.cn",
        "wb.flk.npc.gov.cn",
        "npc.gov.cn",
        "www.npc.gov.cn",
        "cac.gov.cn",
        "www.cac.gov.cn",
        "mee.gov.cn",
        "www.mee.gov.cn",
        "mofcom.gov.cn",
        "www.mofcom.gov.cn",
        "miit.gov.cn",
        "www.miit.gov.cn",
        "samr.gov.cn",
        "www.samr.gov.cn",
        "federalregister.gov",
        "www.federalregister.gov",
        "govinfo.gov",
        "www.govinfo.gov",
        "nist.gov",
        "www.nist.gov",
        "fda.gov",
        "www.fda.gov",
        "fcc.gov",
        "www.fcc.gov",
        "docs.fcc.gov",
        "ftc.gov",
        "www.ftc.gov",
        "cisa.gov",
        "www.cisa.gov",
        "epa.gov",
        "www.epa.gov",
        "fincen.gov",
        "www.fincen.gov",
        "legislation.gov.uk",
        "www.legislation.gov.uk",
        "ofcom.org.uk",
        "www.ofcom.org.uk",
        "etsi.org",
        "www.etsi.org",
        "sec.gov",
        "www.sec.gov",
        "eur-lex.europa.eu",
        "taxation-customs.ec.europa.eu",
        "bis.gov",
        "www.bis.gov",
    }
)

_DOMAIN_METADATA: dict[str, tuple[str, str]] = {
    "gov.cn": ("State Council", "CN"),
    "www.gov.cn": ("State Council", "CN"),
    "flk.npc.gov.cn": ("National People's Congress", "CN"),
    "wb.flk.npc.gov.cn": ("National People's Congress", "CN"),
    "npc.gov.cn": ("National People's Congress", "CN"),
    "www.npc.gov.cn": ("National People's Congress", "CN"),
    "cac.gov.cn": ("Cyberspace Administration of China", "CN"),
    "www.cac.gov.cn": ("Cyberspace Administration of China", "CN"),
    "mee.gov.cn": ("Ministry of Ecology and Environment", "CN"),
    "www.mee.gov.cn": ("Ministry of Ecology and Environment", "CN"),
    "mofcom.gov.cn": ("Ministry of Commerce", "CN"),
    "www.mofcom.gov.cn": ("Ministry of Commerce", "CN"),
    "miit.gov.cn": ("Ministry of Industry and Information Technology", "CN"),
    "www.miit.gov.cn": ("Ministry of Industry and Information Technology", "CN"),
    "samr.gov.cn": ("State Administration for Market Regulation", "CN"),
    "www.samr.gov.cn": ("State Administration for Market Regulation", "CN"),
    "federalregister.gov": ("Federal Register", "US"),
    "www.federalregister.gov": ("Federal Register", "US"),
    "govinfo.gov": ("GovInfo", "US"),
    "www.govinfo.gov": ("GovInfo", "US"),
    "nist.gov": ("National Institute of Standards and Technology", "US"),
    "www.nist.gov": ("National Institute of Standards and Technology", "US"),
    "fda.gov": ("U.S. Food and Drug Administration", "US"),
    "www.fda.gov": ("U.S. Food and Drug Administration", "US"),
    "fcc.gov": ("Federal Communications Commission", "US"),
    "www.fcc.gov": ("Federal Communications Commission", "US"),
    "docs.fcc.gov": ("Federal Communications Commission", "US"),
    "ftc.gov": ("Federal Trade Commission", "US"),
    "www.ftc.gov": ("Federal Trade Commission", "US"),
    "cisa.gov": ("Cybersecurity and Infrastructure Security Agency", "US"),
    "www.cisa.gov": ("Cybersecurity and Infrastructure Security Agency", "US"),
    "epa.gov": ("Environmental Protection Agency", "US"),
    "www.epa.gov": ("Environmental Protection Agency", "US"),
    "fincen.gov": ("Financial Crimes Enforcement Network", "US"),
    "www.fincen.gov": ("Financial Crimes Enforcement Network", "US"),
    "legislation.gov.uk": ("UK legislation", "UK"),
    "www.legislation.gov.uk": ("UK legislation", "UK"),
    "ofcom.org.uk": ("Ofcom", "UK"),
    "www.ofcom.org.uk": ("Ofcom", "UK"),
    "etsi.org": ("European Telecommunications Standards Institute", "EU"),
    "www.etsi.org": ("European Telecommunications Standards Institute", "EU"),
    "sec.gov": ("U.S. Securities and Exchange Commission", "US"),
    "www.sec.gov": ("U.S. Securities and Exchange Commission", "US"),
    "eur-lex.europa.eu": ("European Union", "EU"),
    "taxation-customs.ec.europa.eu": ("European Commission", "EU"),
    "bis.gov": ("U.S. Department of Commerce", "US"),
    "www.bis.gov": ("U.S. Department of Commerce", "US"),
}

_ISO_DATE_RE = re.compile(r"(20\d{2})[-./](\d{2})[-./](\d{2})")
_CHINESE_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_AUTHORITY_RE = re.compile(r"(?:Authority|发布机关|发布单位)[:：]\s*(.+)")
_PUBLICATION_RE = re.compile(r"(?:Publication date|发布日期|发布时间)[:：]\s*([^\n]+)")
_EFFECTIVE_RE = re.compile(r"(?:Effective date|生效日期|施行日期)[:：]\s*([^\n]+)")
_VERSION_RE = re.compile(r"(?:Version|版本)[:：]\s*([^\n]+)")
_TAG_RE = re.compile(r"<[^>]+>")


def is_official_policy_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in OFFICIAL_POLICY_ALLOWLIST


def _strip_markup(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _TAG_RE.sub("", value)
    return " ".join(cleaned.split())


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


def parse_gov_policy_search_response(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    if payload.get("code") == 1001:
        return []
    search_vo = payload.get("searchVO")
    if not isinstance(search_vo, dict):
        return []
    cat_map = search_vo.get("catMap")
    if not isinstance(cat_map, dict):
        return []

    category_priority = {
        "gongwen": 0,
        "bumenfile": 1,
        "gongbao": 2,
        "otherfile": 3,
    }
    records: list[dict[str, object]] = []
    for category_name, bucket in cat_map.items():
        if not isinstance(bucket, dict):
            continue
        items = bucket.get("listVO")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_url = item.get("url")
            title = _strip_markup(str(item.get("title") or ""))
            if not raw_url or not title:
                continue
            url = str(raw_url)
            summary = _strip_markup(str(item.get("summary") or ""))
            pcode = _strip_markup(str(item.get("pcode") or ""))
            authority = _strip_markup(str(item.get("puborg") or "")) or policy_domain_metadata(url)[0]
            jurisdiction = policy_domain_metadata(url)[1]
            snippet = " ".join(part for part in (summary, pcode) if part) or title
            records.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "authority": authority,
                    "jurisdiction": jurisdiction,
                    "publication_date": _normalize_date(str(item.get("pubtimeStr") or "")),
                    "effective_date": None,
                    "version": None,
                    "_category_priority": category_priority.get(category_name, 9),
                }
            )

    records.sort(
        key=lambda item: (
            item["_category_priority"],
            -(int((item["publication_date"] or "0000-00-00").replace("-", ""))),
            item["url"],
        ),
    )
    return records


def preferred_policy_domains(query: str, *, fallback: bool) -> tuple[str, ...]:
    normalized = normalize_query_text(query)

    def _has(*phrases: str) -> bool:
        return any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalize_query_text(phrase))}(?![a-z0-9])",
                normalized,
            )
            for phrase in phrases
        )

    if _has("fcc", "cyber trust mark"):
        primary = ("fcc.gov", "www.fcc.gov", "docs.fcc.gov", "etsi.org", "www.etsi.org")
    elif _has("etsi", "en 303 645"):
        primary = ("etsi.org", "www.etsi.org", "fcc.gov", "www.fcc.gov", "docs.fcc.gov")
    elif (
        _has(
            "ai act",
            "directive",
            "nis2",
            "dsa",
            "dma",
            "data act",
            "battery regulation",
            "cbam",
            "reglement ue",
            "2024 1689",
            "2024/1689",
            "systeme d ia",
            "article officiel",
        )
        or "eu " in normalized
        or "eu-" in normalized
    ):
        primary = ("eur-lex.europa.eu", "taxation-customs.ec.europa.eu")
    elif (
        _has("ofcom", "illegal harms", "codes of practice", "illegal content duties")
    ):
        primary = ("ofcom.org.uk", "legislation.gov.uk")
    elif (
        _has("uk", "united kingdom", "online safety act")
    ):
        primary = ("legislation.gov.uk", "ofcom.org.uk")
    elif _has("fda", "laboratory developed tests", "pccp"):
        primary = ("fda.gov", "federalregister.gov")
    elif _has("ftc", "noncompete"):
        primary = ("ftc.gov", "federalregister.gov")
    elif (
        _has("fincen", "beneficial ownership", "corporate transparency act", "boi")
    ):
        primary = ("fincen.gov", "federalregister.gov")
    elif _has("cisa", "circia", "ransom"):
        primary = ("cisa.gov", "govinfo.gov")
    elif (
        _has("epa", "pfas", "drinking water", "methane rule")
    ):
        primary = ("epa.gov", "federalregister.gov")
    elif _has("nist", "fips"):
        primary = ("nist.gov", "govinfo.gov")
    elif _has("sec", "item 1.05", "cybersecurity disclosure"):
        primary = ("sec.gov", "federalregister.gov")
    elif (
        _has("federal register", "federal", "u.s.", "us", "epa", "methane rule", "cfr")
    ):
        primary = ("federalregister.gov", "govinfo.gov")
    elif _has("export control", "bis"):
        primary = ("bis.gov", "federalregister.gov")
    elif "公司法" in query or "法律" in query or "条例" in query or "司法解释" in query:
        primary = ("flk.npc.gov.cn", "gov.cn")
    else:
        primary = ("gov.cn", "miit.gov.cn", "flk.npc.gov.cn")

    if fallback:
        return primary + ("cac.gov.cn", "samr.gov.cn")
    return primary


def preferred_policy_search_engines(configured_engines: tuple[str, ...]) -> tuple[str, ...]:
    preferred = tuple(
        engine
        for engine in ("bing", "duckduckgo")
        if engine in configured_engines
    )
    if preferred:
        return preferred

    filtered = tuple(
        engine
        for engine in configured_engines
        if engine != "google"
    )
    if filtered:
        return filtered

    return configured_engines[:1] if configured_engines else ("duckduckgo",)
