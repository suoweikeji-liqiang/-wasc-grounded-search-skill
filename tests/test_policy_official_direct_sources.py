"""Direct official-source fallback contracts for policy live adapter."""

from __future__ import annotations

import asyncio


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
