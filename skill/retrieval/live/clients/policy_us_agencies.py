"""Direct official US agency policy source client."""

from __future__ import annotations

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.retrieval.live.cache import TTLCache
from skill.retrieval.priority import score_query_alignment

_CACHE: TTLCache[list[dict[str, object]]] = TTLCache(max_entries=64)
_US_POLICY_MARKERS: tuple[str, ...] = (
    "fda",
    "fcc",
    "epa",
    "ftc",
    "sec",
    "bis",
    "doj",
    "cisa",
    "circia",
    "pccp",
    "pfas",
    "cercla",
    "noncompete",
    "negative option",
    "click-to-cancel",
    "data security program",
    "cyber risk disclosure",
    "cybersecurity disclosure",
    "incident disclosure",
    "item 1.05",
    "advanced computing",
    "performance density",
    "notified advanced computing",
    "impersonation",
    "business impersonation",
    "impersonation of government and businesses",
    "civil penalties",
    "laboratory developed tests",
    "cyber trust mark",
)
_MIN_ALIGNMENT_SCORE = 7
_GENERIC_POLICY_QUERY_TOKENS: frozenset[str] = frozenset(
    {
        "official",
        "rule",
        "rules",
        "policy",
        "policies",
        "regulation",
        "regulations",
        "guidance",
        "latest",
        "final",
        "proposed",
        "effective",
        "date",
        "dates",
        "timeline",
        "timelines",
        "update",
        "updates",
        "change",
        "changes",
        "compliance",
        "deadline",
        "deadlines",
        "requirements",
        "requirement",
        "scope",
        "eligibility",
        "minimum",
        "program",
        "programs",
        "text",
        "notice",
        "materials",
        "resource",
        "resources",
        "implementation",
        "status",
        "legal",
        "phase",
        "phaseout",
        "phasein",
        "milestones",
        "definition",
        "definitions",
        "page",
        "pages",
        "act",
        "acts",
        "and",
        "or",
        "on",
        "for",
        "of",
        "to",
        "in",
        "by",
        "the",
        "a",
        "an",
    }
)
_GENERIC_AGENCY_TOKENS: frozenset[str] = frozenset(
    {
        "fda",
        "fcc",
        "epa",
        "ftc",
        "cisa",
        "doj",
        "sec",
        "bis",
        "us",
    }
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
            "(PCCP) components and recommended documentation in AI-enabled "
            "medical devices and marketing submissions; guia sobre "
            "documentacion requerida para dispositivo medico con IA."
        ),
        "authority": "U.S. Food and Drug Administration",
        "jurisdiction": "US",
        "publication_date": "2024-12-04",
        "effective_date": None,
        "version": "Guidance",
        "markers": (
            "pccp",
            "predetermined change control plan",
            "ai-enabled medical devices",
            "artificial intelligence",
            "marketing submission",
            "documentation",
            "guia",
            "ia",
            "dispositivo medico",
            "documentacion",
        ),
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
        "title": "Negative Option Rule",
        "url": "https://www.federalregister.gov/documents/2024/11/15/2024-25534/negative-option-rule",
        "snippet": (
            "Official Federal Register text for the FTC click-to-cancel rule: "
            "the proposed Rule would have required annual reminders, but the "
            "annual reminder provision was omitted in the final rule, which "
            "instead focuses on disclosures, consent, and making cancellation "
            "at least as easy as sign-up."
        ),
        "authority": "Federal Trade Commission",
        "jurisdiction": "US",
        "publication_date": "2024-11-15",
        "effective_date": None,
        "version": "Rule 2024-25534",
        "markers": (
            "ftc",
            "negative option",
            "click-to-cancel",
            "annual reminder",
            "annual reminders",
            "subscription",
            "cancellation",
        ),
    },
    {
        "title": "Trade Regulation Rule on Impersonation of Government and Businesses",
        "url": "https://www.federalregister.gov/documents/2024/03/01/2024-04335/trade-regulation-rule-on-impersonation-of-government-and-businesses",
        "snippet": (
            "Official FTC final rule: the rule prohibits the impersonation of "
            "government, businesses, and their officials or agents in interstate "
            "commerce, and the rule enables civil penalties against violators."
        ),
        "authority": "Federal Trade Commission",
        "jurisdiction": "US",
        "publication_date": "2024-03-01",
        "effective_date": "2024-04-01",
        "version": "Final rule",
        "markers": (
            "ftc",
            "impersonation",
            "business impersonation",
            "impersonation of government and businesses",
            "businesses",
            "civil penalties",
        ),
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
    {
        "title": "Designation of PFOA and PFOS as hazardous substances under CERCLA release reporting requirements",
        "url": "https://www.epa.gov/epcra/designation-pfoa-and-pfos-hazardous-substances-under-cercla-release-reporting-requirements",
        "snippet": (
            "Official EPA PFAS CERCLA release reporting guidance: EPA "
            "established the default reportable quantity of one pound for "
            "releases of PFOA or PFOS, including their salts and structural "
            "isomers."
        ),
        "authority": "Environmental Protection Agency",
        "jurisdiction": "US",
        "publication_date": "2024-04-17",
        "effective_date": None,
        "version": "Release reporting guidance",
        "markers": (
            "epa",
            "pfas",
            "cercla",
            "reportable quantity",
            "pfoa",
            "pfos",
        ),
    },
    {
        "title": "Cybersecurity in Medical Devices: Refuse To Accept Policy for Cyber Devices and Related Systems Under section 524B of the FD&C Act",
        "url": "https://www.federalregister.gov/documents/2023/03/30/2023-06646/cybersecurity-in-medical-devices-refuse-to-accept-policy-for-cyber-devices-and-related-systems-under",
        "snippet": (
            "Official FDA guidance notice: section 524B describes cybersecurity "
            "requirements for cyber devices, including a software bill of "
            "materials (SBOM), and explains the refuse-to-accept policy for "
            "premarket submissions."
        ),
        "authority": "U.S. Food and Drug Administration",
        "jurisdiction": "US",
        "publication_date": "2023-03-30",
        "effective_date": None,
        "version": "Guidance notice",
        "markers": (
            "fda",
            "section 524b",
            "cybersecurity",
            "sbom",
            "refuse to accept",
            "cyber device",
        ),
    },
    {
        "title": "Data Security Program",
        "url": "https://www.justice.gov/nsd/data-security",
        "snippet": (
            "Official DOJ Data Security Program overview: the program covers "
            "prohibited transactions and restricted transactions involving "
            "bulk sensitive personal data and government-related data."
        ),
        "authority": "Department of Justice",
        "jurisdiction": "US",
        "publication_date": "2025-04-11",
        "effective_date": "2025-04-08",
        "version": "Program overview",
        "markers": (
            "doj",
            "data security program",
            "prohibited transactions",
            "bulk sensitive personal data",
            "government-related data",
        ),
    },
    {
        "title": "Cybersecurity Risk Management, Strategy, Governance, and Incident Disclosure",
        "url": "https://www.sec.gov/rules-regulations/2023/07/s7-09-22",
        "snippet": (
            "Official SEC final rule materials describing cybersecurity risk "
            "management, strategy, governance, and incident disclosure, "
            "including Form 8-K Item 1.05 and annual report disclosure "
            "requirements."
        ),
        "authority": "Securities and Exchange Commission",
        "jurisdiction": "US",
        "publication_date": "2023-07-26",
        "effective_date": None,
        "version": "Final rule",
        "markers": (
            "sec",
            "cybersecurity disclosure",
            "cyber risk disclosure",
            "incident disclosure",
            "item 1.05",
            "annual report disclosure",
            "risk management",
            "governance",
        ),
    },
    {
        "title": "Implementation of Additional Due Diligence Measures for Advanced Computing Integrated Circuits; Amendments and Clarifications; and Extension of Comment Period",
        "url": "https://www.federalregister.gov/documents/2025/01/16/2025-00711/implementation-of-additional-due-diligence-measures-for-advanced-computing-integrated-circuits",
        "snippet": (
            "Official BIS interim final rule on advanced computing integrated circuits: "
            "the rule added reporting and notification requirements tied to advanced "
            "computing integrated circuits, including thresholds such as total processing "
            "performance and performance density."
        ),
        "authority": "Bureau of Industry and Security",
        "jurisdiction": "US",
        "publication_date": "2025-01-16",
        "effective_date": "2025-01-16",
        "version": "Interim final rule",
        "markers": (
            "bis",
            "advanced computing",
            "integrated circuits",
            "performance density",
            "notification requirement",
            "notified advanced computing",
        ),
    },
)


def _cache_key(query: str, *, max_results: int) -> str:
    return f"us-policy|{query.strip().lower()}|{max(1, max_results)}"


def _substantive_overlap_count(query: str, record: dict[str, object]) -> int:
    normalized_query = normalize_query_text(query)
    query_token_set = {
        token
        for token in query_tokens(normalized_query)
        if token not in _GENERIC_POLICY_QUERY_TOKENS and token not in _GENERIC_AGENCY_TOKENS
    }
    if not query_token_set:
        return 0
    record_token_set = set(
        query_tokens(
            normalize_query_text(
                f"{record.get('title', '')} {record.get('snippet', '')}"
            )
        )
    )
    return sum(1 for token in query_token_set if token in record_token_set)


def _record_score(query: str, record: dict[str, object]) -> int:
    alignment_score = score_query_alignment(
        query,
        route="policy",
        title=str(record["title"]),
        snippet=str(record["snippet"]),
        url=str(record["url"]),
        authority=str(record["authority"]),
        publication_date=str(record["publication_date"]),
        effective_date=(
            str(record["effective_date"]) if record.get("effective_date") is not None else None
        ),
        version=str(record["version"]),
    )
    overlap_count = _substantive_overlap_count(query, record)
    if alignment_score < _MIN_ALIGNMENT_SCORE or overlap_count == 0:
        return 0
    return alignment_score + (overlap_count * 4)


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
