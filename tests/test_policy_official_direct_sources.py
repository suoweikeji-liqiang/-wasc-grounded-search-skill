"""Direct official-source fallback contracts for policy live adapter."""

from __future__ import annotations

import asyncio


def test_eur_lex_direct_source_matches_french_ai_act_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query="FR reglement UE 2024 1689 definition systeme d IA article officiel",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["url"] == "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
    assert hits[0]["authority"] == "European Union"
    assert hits[0]["jurisdiction"] == "EU"


def test_us_agency_direct_source_matches_fcc_cyber_trust_mark_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query=(
                "FCC Cyber Trust Mark minimum security requirements eligibility "
                "scope official"
            ),
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Federal Communications Commission"
    assert hits[0]["jurisdiction"] == "US"
    assert "fcc.gov" in hits[0]["url"]


def test_us_agency_direct_source_filters_out_unrelated_us_policy_records() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FCC Cyber Trust Mark minimum security requirements eligibility scope official",
            max_results=5,
        )
    )

    assert hits == [
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
        }
    ]


def test_us_agency_direct_source_matches_fda_inspection_classification_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FDA CGMP inspection classification OAI VAI NAI definitions official",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "U.S. Food and Drug Administration"
    assert hits[0]["jurisdiction"] == "US"
    assert "inspection" in hits[0]["title"].lower()
    assert "fda.gov" in hits[0]["url"]


def test_us_agency_direct_source_drops_unrelated_ftc_catalog_hit_for_rule_name_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FTC junk fees disclosure rule",
            max_results=5,
        )
    )

    assert hits == []


def test_us_agency_direct_source_preserves_true_noncompete_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FTC noncompete rule senior executives official",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["title"] == "Non-Compete Clause Rule"
    assert hits[0]["authority"] == "Federal Trade Commission"


def test_us_agency_direct_source_matches_ftc_negative_option_annual_reminder_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FTC click-to-cancel negative option rule annual reminder requirement official text",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["title"] == "Negative Option Rule"
    assert "annual reminders" in hits[0]["snippet"].lower()
    assert "omitted in the final rule" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_ftc_click_to_cancel_update_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FTC click-to-cancel rule and streaming platform subscription flow redesign update",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["title"] == "Negative Option Rule"
    assert "click-to-cancel" in hits[0]["snippet"].lower()
    assert "cancel" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_epa_pfas_cercla_reportable_quantity_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="EPA PFAS CERCLA hazardous substance reportable quantity official",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Environmental Protection Agency"
    assert "one pound" in hits[0]["snippet"].lower()
    assert "reportable quantity" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_doj_data_security_program_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="DOJ data security program prohibited transactions bulk sensitive personal data official rule",
            max_results=5,
        )
    )

    assert hits
    assert "justice.gov" in hits[0]["url"]
    assert "bulk sensitive personal data" in hits[0]["snippet"].lower()
    assert "prohibited" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_fda_section_524b_sbom_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FDA section 524B cybersecurity SBOM requirement official guidance",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "U.S. Food and Drug Administration"
    assert "section 524b" in hits[0]["snippet"].lower()
    assert "sbom" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_spanish_fda_pccp_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="ES guia FDA PCCP IA dispositivo medico documentacion requerida oficial",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["title"].startswith("Predetermined Change Control Plan")
    assert "documentation" in hits[0]["snippet"].lower()
    assert "medical devices" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_sec_cyber_risk_disclosure_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="SEC annual cyber risk disclosure expectations and company 10-K risk factor wording update",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Securities and Exchange Commission"
    assert "item 1.05" in hits[0]["snippet"].lower()
    assert "incident disclosure" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_bis_advanced_computing_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="BIS advanced computing rule performance density notification requirement official text",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Bureau of Industry and Security"
    assert "performance density" in hits[0]["snippet"].lower()
    assert "notification" in hits[0]["snippet"].lower()


def test_us_agency_direct_source_matches_ftc_impersonation_query() -> None:
    from skill.retrieval.live.clients.policy_us_agencies import search_us_policy_agencies

    hits = asyncio.run(
        search_us_policy_agencies(
            query="FTC impersonation rule business-to-business scope civil penalties official text",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["title"] == "Trade Regulation Rule on Impersonation of Government and Businesses"
    assert "businesses" in hits[0]["snippet"].lower()
    assert "civil penalties" in hits[0]["snippet"].lower()


def test_uk_direct_source_matches_ofcom_illegal_harms_codes_query() -> None:
    from skill.retrieval.live.clients.policy_uk_legislation import search_uk_legislation

    hits = asyncio.run(
        search_uk_legislation(
            query=(
                "Ofcom illegal harms codes of practice online safety act "
                "compliance milestones official"
            ),
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Ofcom"
    assert hits[0]["jurisdiction"] == "UK"
    assert hits[0]["url"].startswith("https://www.ofcom.org.uk/")


def test_uk_direct_source_matches_psti_no_default_passwords_query() -> None:
    from skill.retrieval.live.clients.policy_uk_legislation import search_uk_legislation

    hits = asyncio.run(
        search_uk_legislation(
            query="UK PSTI Act no default passwords compliance date official guidance",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["authority"] == "Office for Product Safety and Standards"
    assert hits[0]["jurisdiction"] == "UK"
    assert "29 april 2024" in hits[0]["snippet"].lower()
    assert "guessable passwords" in hits[0]["snippet"].lower()


def test_eur_lex_direct_source_matches_data_act_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query=(
                "EU Data Act application date connected products data holder "
                "obligations trade-secret safeguards official"
            ),
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["url"] == "https://eur-lex.europa.eu/eli/reg/2023/2854/oj/eng"
    assert hits[0]["authority"] == "European Union"
    assert hits[0]["jurisdiction"] == "EU"


def test_eur_lex_direct_source_matches_dora_major_ict_incident_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query="EU DORA major ICT incident initial notification deadline official text",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["url"] == "https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng"
    assert "initial notification" in hits[0]["snippet"].lower()
    assert "same business day" in hits[0]["snippet"].lower()


def test_eur_lex_direct_source_matches_cyber_resilience_act_reporting_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query="EU Cyber Resilience Act vulnerability exploitation reporting obligation official text",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["url"] == "https://eur-lex.europa.eu/eli/reg/2024/2847/oj/eng"
    assert "24 hours" in hits[0]["snippet"]


def test_eur_lex_direct_source_matches_cbam_default_values_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query="CBAM default values use conditions embedded emissions official text",
            max_results=5,
        )
    )

    assert hits
    assert "default values" in hits[0]["snippet"].lower()
    assert "embedded emissions" in hits[0]["snippet"].lower()


def test_eur_lex_direct_source_matches_cbam_authorised_declarant_query() -> None:
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex

    hits = asyncio.run(
        search_eur_lex(
            query="FR declarant CBAM autorise definition texte officiel",
            max_results=5,
        )
    )

    assert hits
    assert hits[0]["url"] == "https://eur-lex.europa.eu/eli/reg/2023/956/oj/eng"
    assert "authorised cbam declarant" in hits[0]["snippet"].lower()
    assert "embedded emissions" in hits[0]["snippet"].lower()


def test_policy_registry_live_adapter_uses_eur_lex_direct_source_for_french_ai_act_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.policy_eur_lex import search_eur_lex as actual_search_eur_lex

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FR reglement UE 2024 1689 definition systeme d IA article officiel"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "FR reglement UE 2024 1689 definition systeme d IA article officiel"
        del config
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", actual_search_eur_lex)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        adapter.search_live("FR reglement UE 2024 1689 definition systeme d IA article officiel")
    )

    assert len(hits) == 1
    assert hits[0].url == "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
    assert hits[0].authority == "European Union"
    assert hits[0].jurisdiction == "EU"


def test_policy_registry_live_adapter_skips_irrelevant_fixture_shortcut_for_ofcom_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.policy_uk_legislation import (
        search_uk_legislation as actual_search_uk_legislation,
    )

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert (
            query
            == "UK Online Safety Act Ofcom 2025 2026 compliance milestones illegal harms codes and platform policy changes tied to Ofcom codes"
        )
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert (
            query
            == "UK Online Safety Act Ofcom 2025 2026 compliance milestones illegal harms codes and platform policy changes tied to Ofcom codes"
        )
        del config
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(
        adapter,
        "_FIXTURES",
        (
            {
                "title": "Platform policy changes and compliance milestones bulletin",
                "url": "https://www.mee.gov.cn/policy/latest-regulation",
                "snippet": "2025 2026 compliance milestones tied to platform policy changes and codes.",
                "authority": "Ministry of Ecology and Environment",
                "jurisdiction": "CN",
                "publication_date": "2026-03-18",
                "effective_date": "2026-04-01",
                "version": "2026 bulletin",
            },
        ),
    )
    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_uk_legislation", actual_search_uk_legislation)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _empty_direct)

    hits = asyncio.run(
        adapter.search_live(
            "UK Online Safety Act Ofcom 2025 2026 compliance milestones illegal harms codes and platform policy changes tied to Ofcom codes"
        )
    )

    assert hits
    assert hits[0].authority == "Ofcom"
    assert hits[0].jurisdiction == "UK"
    assert hits[0].url.startswith("https://www.ofcom.org.uk/")


def test_policy_registry_live_adapter_uses_eur_lex_direct_source_when_discovery_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "NIS2 Directive transposition deadline official text"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "NIS2 Directive transposition deadline official text"
        del config
        return []

    async def _fake_search_eur_lex(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "NIS2 Directive transposition deadline official text"
        assert max_results == 5
        return [
            {
                "title": "Directive (EU) 2022/2555 (NIS2 Directive)",
                "url": "https://eur-lex.europa.eu/eli/dir/2022/2555/2022-12-27/eng",
                "snippet": "Official NIS2 text with transposition deadline 2024-10-17.",
                "authority": "European Union",
                "jurisdiction": "EU",
                "publication_date": "2022-12-27",
                "effective_date": None,
                "version": "Official Journal text",
            }
        ]

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", _fake_search_eur_lex)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(adapter.search_live("NIS2 Directive transposition deadline official text"))

    assert len(hits) == 1
    assert hits[0].url == "https://eur-lex.europa.eu/eli/dir/2022/2555/2022-12-27/eng"
    assert hits[0].authority == "European Union"
    assert hits[0].jurisdiction == "EU"


def test_policy_registry_live_adapter_uses_nist_direct_source_when_other_sources_miss(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FIPS 204 final publication date"
        assert max_results == 5
        return []

    async def _empty_search_federal_register(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FIPS 204 final publication date"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "FIPS 204 final publication date"
        del config
        return []

    async def _fake_search_nist(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FIPS 204 final publication date"
        assert max_results == 5
        return [
            {
                "title": "FIPS 204, Module-Lattice-Based Digital Signature Standard",
                "url": "https://csrc.nist.gov/pubs/fips/204/final",
                "snippet": "Official NIST FIPS 204 final publication page.",
                "authority": "National Institute of Standards and Technology",
                "jurisdiction": "US",
                "publication_date": "2024-08-13",
                "effective_date": None,
                "version": "Final",
            }
        ]

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_nist_publications", _fake_search_nist)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(adapter.search_live("FIPS 204 final publication date"))

    assert len(hits) == 1
    assert hits[0].url == "https://csrc.nist.gov/pubs/fips/204/final"
    assert hits[0].authority == "National Institute of Standards and Technology"
    assert hits[0].jurisdiction == "US"


def test_policy_registry_live_adapter_uses_uk_legislation_direct_source_when_discovery_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "UK Online Safety Act official text commencement"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "UK Online Safety Act official text commencement"
        del config
        return []

    async def _fake_search_uk_legislation(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "UK Online Safety Act official text commencement"
        assert max_results == 5
        return [
            {
                "title": "Online Safety Act 2023",
                "url": "https://www.legislation.gov.uk/ukpga/2023/50/contents",
                "snippet": "Official UK legislation database text for Online Safety Act 2023.",
                "authority": "UK legislation",
                "jurisdiction": "UK",
                "publication_date": "2023-10-26",
                "effective_date": None,
                "version": "As enacted",
            }
        ]

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_uk_legislation", _fake_search_uk_legislation)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(adapter.search_live("UK Online Safety Act official text commencement"))

    assert len(hits) == 1
    assert hits[0].url == "https://www.legislation.gov.uk/ukpga/2023/50/contents"
    assert hits[0].authority == "UK legislation"
    assert hits[0].jurisdiction == "UK"


def test_policy_registry_live_adapter_returns_direct_us_source_without_waiting_for_slow_registry_when_query_is_direct_favored(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _slow_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "EPA PFAS CERCLA hazardous substance reportable quantity official"
        assert max_results == 5
        await asyncio.sleep(10)
        return []

    async def _fake_search_us_policy_agencies(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "EPA PFAS CERCLA hazardous substance reportable quantity official"
        assert max_results == 5
        return [
            {
                "title": "Designation of PFOA and PFOS as hazardous substances under CERCLA release reporting requirements",
                "url": "https://www.epa.gov/epcra/designation-pfoa-and-pfos-hazardous-substances-under-cercla-release-reporting-requirements",
                "snippet": "Official EPA PFAS CERCLA release reporting guidance: EPA established the default reportable quantity of one pound for releases of PFOA or PFOS, including their salts and structural isomers.",
                "authority": "Environmental Protection Agency",
                "jurisdiction": "US",
                "publication_date": "2024-04-17",
                "effective_date": None,
                "version": "Release reporting guidance",
            }
        ]

    async def _empty_search_federal_register(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _empty_search_open_web_policy(
        **_: object,
    ) -> list[dict[str, object]]:
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _slow_search_policy_registry)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _fake_search_us_policy_agencies)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live("EPA PFAS CERCLA hazardous substance reportable quantity official"),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].authority == "Environmental Protection Agency"
    assert "one pound" in hits[0].snippet.lower()


def test_policy_registry_live_adapter_returns_direct_sec_source_for_cyber_disclosure_query(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _slow_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "SEC annual cyber risk disclosure expectations and company 10-K risk factor wording update"
        assert max_results == 5
        await asyncio.sleep(10)
        return []

    async def _fake_search_us_policy_agencies(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "SEC annual cyber risk disclosure expectations and company 10-K risk factor wording update"
        assert max_results == 5
        return [
            {
                "title": "Cybersecurity Risk Management, Strategy, Governance, and Incident Disclosure",
                "url": "https://www.sec.gov/rules-regulations/2023/07/s7-09-22",
                "snippet": "Official SEC final rule materials describing cybersecurity risk management, strategy, governance, and incident disclosure, including Form 8-K Item 1.05 and annual report disclosure requirements.",
                "authority": "Securities and Exchange Commission",
                "jurisdiction": "US",
                "publication_date": "2023-07-26",
                "effective_date": None,
                "version": "Final rule",
            }
        ]

    async def _empty_search_federal_register(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_search_open_web_policy(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _slow_search_policy_registry)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _fake_search_us_policy_agencies)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "SEC annual cyber risk disclosure expectations and company 10-K risk factor wording update"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].authority == "Securities and Exchange Commission"
    assert "item 1.05" in hits[0].snippet.lower()


def test_policy_registry_live_adapter_returns_direct_bis_source_when_query_is_direct_favored(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _slow_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "BIS advanced computing rule performance density notification requirement official text"
        assert max_results == 5
        await asyncio.sleep(10)
        return []

    async def _fake_search_us_policy_agencies(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "BIS advanced computing rule performance density notification requirement official text"
        assert max_results == 5
        return [
            {
                "title": "Implementation of Additional Due Diligence Measures for Advanced Computing Integrated Circuits; Amendments and Clarifications; and Extension of Comment Period",
                "url": "https://www.federalregister.gov/documents/2025/01/16/2025-00711/implementation-of-additional-due-diligence-measures-for-advanced-computing-integrated-circuits",
                "snippet": "Official BIS interim final rule on advanced computing integrated circuits: the rule added reporting and notification requirements tied to advanced computing integrated circuits, including thresholds such as total processing performance and performance density.",
                "authority": "Bureau of Industry and Security",
                "jurisdiction": "US",
                "publication_date": "2025-01-16",
                "effective_date": "2025-01-16",
                "version": "Interim final rule",
            }
        ]

    async def _empty_search_federal_register(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_search_open_web_policy(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _slow_search_policy_registry)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _fake_search_us_policy_agencies)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "BIS advanced computing rule performance density notification requirement official text"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].authority == "Bureau of Industry and Security"
    assert "performance density" in hits[0].snippet.lower()


def test_policy_registry_live_adapter_returns_direct_ftc_impersonation_source_when_query_is_direct_favored(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _slow_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FTC impersonation rule business-to-business scope civil penalties official text"
        assert max_results == 5
        await asyncio.sleep(10)
        return []

    async def _fake_search_us_policy_agencies(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FTC impersonation rule business-to-business scope civil penalties official text"
        assert max_results == 5
        return [
            {
                "title": "Trade Regulation Rule on Impersonation of Government and Businesses",
                "url": "https://www.federalregister.gov/documents/2024/03/01/2024-04335/trade-regulation-rule-on-impersonation-of-government-and-businesses",
                "snippet": "Official FTC final rule: the rule prohibits the impersonation of government, businesses, and their officials or agents in interstate commerce, and the rule enables civil penalties against violators.",
                "authority": "Federal Trade Commission",
                "jurisdiction": "US",
                "publication_date": "2024-03-01",
                "effective_date": "2024-04-01",
                "version": "Final rule",
            }
        ]

    async def _empty_search_federal_register(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_search_open_web_policy(**_: object) -> list[dict[str, object]]:
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _slow_search_policy_registry)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _fake_search_us_policy_agencies)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        asyncio.wait_for(
            adapter.search_live(
                "FTC impersonation rule business-to-business scope civil penalties official text"
            ),
            timeout=1.0,
        )
    )

    assert len(hits) == 1
    assert hits[0].authority == "Federal Trade Commission"
    assert "civil penalties" in hits[0].snippet.lower()


def test_policy_registry_live_adapter_uses_psti_direct_source_when_discovery_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "UK PSTI Act no default passwords compliance date official guidance"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "UK PSTI Act no default passwords compliance date official guidance"
        del config
        return []

    async def _fake_search_uk_legislation(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "UK PSTI Act no default passwords compliance date official guidance"
        assert max_results == 5
        return [
            {
                "title": "Regulations: consumer connectable product security",
                "url": "https://www.gov.uk/guidance/regulations-consumer-connectable-product-security",
                "snippet": "Official UK PSTI guidance: the consumer connectable product security regime came into effect on 29 April 2024, and the security requirements include banning universal default and easily guessable passwords.",
                "authority": "Office for Product Safety and Standards",
                "jurisdiction": "UK",
                "publication_date": "2024-01-08",
                "effective_date": "2024-04-29",
                "version": "Guidance",
            }
        ]

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_uk_legislation", _fake_search_uk_legislation)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        adapter.search_live("UK PSTI Act no default passwords compliance date official guidance")
    )

    assert len(hits) == 1
    assert hits[0].authority == "Office for Product Safety and Standards"
    assert "29 april 2024" in hits[0].snippet.lower()


def test_policy_registry_live_adapter_uses_us_agency_direct_source_when_discovery_misses(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FDA final rule laboratory developed tests phase-in timeline official"
        assert max_results == 5
        return []

    async def _empty_search_federal_register(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FDA final rule laboratory developed tests phase-in timeline official"
        assert max_results == 5
        return []

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "FDA final rule laboratory developed tests phase-in timeline official"
        del config
        return []

    async def _fake_search_us_agencies(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FDA final rule laboratory developed tests phase-in timeline official"
        assert max_results == 5
        return [
            {
                "title": "Medical Devices; Laboratory Developed Tests (LDTs)",
                "url": "https://www.federalregister.gov/documents/2024/05/06/2024-09737/medical-devices-laboratory-developed-tests",
                "snippet": "Official FDA final rule for laboratory developed tests with staged phaseout timeline.",
                "authority": "U.S. Food and Drug Administration",
                "jurisdiction": "US",
                "publication_date": "2024-05-06",
                "effective_date": "2024-07-05",
                "version": "Final rule",
            }
        ]

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_federal_register", _empty_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", _fake_search_us_agencies)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(
        adapter.search_live("FDA final rule laboratory developed tests phase-in timeline official")
    )

    assert len(hits) == 1
    assert hits[0].authority == "U.S. Food and Drug Administration"
    assert hits[0].jurisdiction == "US"


def test_policy_registry_live_adapter_drops_weak_us_agency_fallback_when_federal_register_times_out(
    monkeypatch,
) -> None:
    import skill.retrieval.adapters.policy_official_registry as adapter
    from skill.retrieval.live.clients.policy_us_agencies import (
        search_us_policy_agencies as actual_search_us_policy_agencies,
    )

    async def _empty_search_policy_registry(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FTC junk fees disclosure rule"
        assert max_results == 5
        return []

    async def _timeout_search_federal_register(
        *,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, object]]:
        assert query == "FTC junk fees disclosure rule"
        assert max_results == 5
        raise TimeoutError

    async def _empty_search_open_web_policy(
        *,
        query: str,
        config,
    ) -> list[dict[str, object]]:
        assert query == "FTC junk fees disclosure rule"
        del config
        return []

    async def _empty_direct(**_: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(adapter, "search_policy_registry", _empty_search_policy_registry)
    monkeypatch.setattr(adapter, "search_federal_register", _timeout_search_federal_register)
    monkeypatch.setattr(adapter, "_search_open_web_policy", _empty_search_open_web_policy)
    monkeypatch.setattr(adapter, "search_us_policy_agencies", actual_search_us_policy_agencies)
    monkeypatch.setattr(adapter, "search_eur_lex", _empty_direct)
    monkeypatch.setattr(adapter, "search_nist_publications", _empty_direct)
    monkeypatch.setattr(adapter, "search_fincen_policy", _empty_direct)
    monkeypatch.setattr(adapter, "search_uk_legislation", _empty_direct)
    monkeypatch.setattr(adapter, "_rank_fixture_records", lambda **_: [])

    hits = asyncio.run(adapter.search_live("FTC junk fees disclosure rule"))

    assert hits == []
