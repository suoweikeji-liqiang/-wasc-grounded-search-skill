"""Direct official US agency policy source client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.cache import TTLCache

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_US_POLICY_MARKERS: tuple[str, ...] = (
    "fda",
    "fcc",
    "epa",
    "ftc",
    "cisa",
    "circia",
    "pccp",
    "pfas",
    "noncompete",
    "laboratory developed tests",
    "cyber trust mark",
)
_CATALOG: tuple[dict[str, object], ...] = (
    {
        "title": "U.S. Cyber Trust Mark",
        "url": "https://www.fcc.gov/CyberTrustMark",
        "snippet": (
            "Official FCC landing page for the U.S. Cyber Trust Mark labeling "
            "program, including eligibility scope and baseline cybersecurity "
            "requirements for wireless consumer IoT products."
        ),
        "authority": "Federal Communications Commission",
        "jurisdiction": "US",
        "publication_date": "2024-03-14",
        "effective_date": None,
        "version": "Program page",
        "markers": (
            "fcc",
            "cyber trust mark",
            "eligibility",
            "wireless consumer iot",
            "minimum security requirements",
        ),
    },
    {
        "title": "Medical Devices; Laboratory Developed Tests (LDTs)",
        "url": "https://www.federalregister.gov/documents/2024/05/06/2024-09737/medical-devices-laboratory-developed-tests",
        "snippet": (
            "Official final rule for laboratory developed tests with staged "
            "phaseout policy and compliance timeline."
        ),
        "authority": "U.S. Food and Drug Administration",
        "jurisdiction": "US",
        "publication_date": "2024-05-06",
        "effective_date": "2024-07-05",
        "version": "Final rule",
        "markers": ("laboratory developed tests", "ldt", "mdr correction removal reporting"),
    },
    {
        "title": "Predetermined Change Control Plan (PCCP) for AI-Enabled Device Software Functions",
        "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence-enabled",
        "snippet": (
            "Official FDA guidance for Predetermined Change Control Plan "
            "(PCCP) components in AI-enabled medical devices."
        ),
        "authority": "U.S. Food and Drug Administration",
        "jurisdiction": "US",
        "publication_date": "2024-12-04",
        "effective_date": None,
        "version": "Guidance",
        "markers": ("pccp", "predetermined change control plan"),
    },
    {
        "title": "Compliance Program Guidance Manual 7382.845 - Inspections of Licensed Biological Therapeutic Drug Products",
        "url": "https://www.fda.gov/media/71878/download",
        "snippet": (
            "Official FDA inspection classifications reference defining NAI, "
            "VAI, and OAI outcomes for CGMP inspections."
        ),
        "authority": "U.S. Food and Drug Administration",
        "jurisdiction": "US",
        "publication_date": "2022-10-01",
        "effective_date": None,
        "version": "Compliance Program Guidance Manual",
        "markers": ("cgmp", "inspection classification", "oai", "vai", "nai"),
    },
    {
        "title": "National Primary Drinking Water Regulation for PFAS",
        "url": "https://www.epa.gov/sdwa/and-polyfluoroalkyl-substances-pfas",
        "snippet": "Official EPA PFAS drinking water regulation summary and compliance milestones.",
        "authority": "Environmental Protection Agency",
        "jurisdiction": "US",
        "publication_date": "2024-04-10",
        "effective_date": "2024-06-25",
        "version": "Final rule resources",
        "markers": ("epa", "pfas", "drinking water", "monitoring deadlines"),
    },
    {
        "title": "Non-Compete Clause Rule",
        "url": "https://www.ftc.gov/legal-library/browse/rules/noncompete-rule",
        "snippet": (
            "Official FTC noncompete rule materials including implementation and "
            "legal-status updates."
        ),
        "authority": "Federal Trade Commission",
        "jurisdiction": "US",
        "publication_date": "2024-04-23",
        "effective_date": "2024-09-04",
        "version": "Final rule",
        "markers": ("ftc", "noncompete", "non-compete", "senior executives"),
    },
    {
        "title": "Cyber Incident Reporting for Critical Infrastructure Act of 2022 (CIRCIA)",
        "url": "https://www.cisa.gov/resources-tools/resources/cyber-incident-reporting-critical-infrastructure-act-2022-circia",
        "snippet": (
            "Official CISA CIRCIA resources on reporting timelines for covered "
            "cyber incidents and ransomware payments."
        ),
        "authority": "Cybersecurity and Infrastructure Security Agency",
        "jurisdiction": "US",
        "publication_date": "2024-04-04",
        "effective_date": None,
        "version": "Notice of proposed rulemaking resources",
        "markers": ("cisa", "circia", "reporting deadlines", "ransom payments"),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"us-policy|{query.strip().lower()}|{max(1, max_results)}"


def _record_score(query: str, record: dict[str, object]) -> int:
    normalized = query.lower()
    markers = tuple(str(item).lower() for item in record.get("markers", ()))
    marker_hits = sum(1 for marker in markers if marker and marker in normalized)
    return marker_hits


def _materialize(record: dict[str, object]) -> dict[str, object]:
    return {
        "title": str(record["title"]),
        "url": str(record["url"]),
        "snippet": str(record["snippet"]),
        "authority": str(record["authority"]),
        "jurisdiction": str(record["jurisdiction"]),
        "publication_date": str(record["publication_date"]),
        "effective_date": (
            str(record["effective_date"]) if record.get("effective_date") is not None else None
        ),
        "version": str(record["version"]),
    }


async def search_us_policy_agencies(
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, object]]:
    """Return direct official US policy pages for FDA/FTC/EPA/CISA-style queries."""
    config = LiveRetrievalConfig.from_env()
    key = _cache_key(query, max_results=max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    normalized_query = query.strip().lower()
    if not any(marker in normalized_query for marker in _US_POLICY_MARKERS):
        return []

    ranked = sorted(
        (
            (score, record)
            for record in _CATALOG
            if (score := _record_score(normalized_query, record)) > 0
        ),
        key=lambda item: (item[0], str(item[1]["publication_date"]), str(item[1]["url"])),
        reverse=True,
    )
    results = [_materialize(record) for _, record in ranked[: max(1, max_results)]]
    _CACHE.set(key, results, ttl_seconds=config.search_cache_ttl_seconds)
    return results
