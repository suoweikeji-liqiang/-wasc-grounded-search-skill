"""Retrieval integration regressions for runtime orchestration and API wiring."""

from __future__ import annotations

import asyncio

import pytest

from fastapi.testclient import TestClient

from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import RetrievalExecutionOutcome
from skill.retrieval.models import RetrievalHit


def _outcome(*hits: RetrievalHit) -> RetrievalExecutionOutcome:
    return RetrievalExecutionOutcome(
        status="success",
        failure_reason=None,
        gaps=(),
        results=hits,
        source_results=(),
    )


def _policy_hit(
    *,
    source_id: str = "policy_official_registry",
    title: str,
    url: str,
    snippet: str,
    authority: str,
    jurisdiction: str | None = None,
    publication_date: str | None = None,
    effective_date: str | None = None,
    version: str | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        source_id=source_id,
        title=title,
        url=url,
        snippet=snippet,
        credibility_tier="official_government",
        authority=authority,
        jurisdiction=jurisdiction,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
    )


def _academic_hit(
    *,
    source_id: str,
    title: str,
    url: str,
    snippet: str,
    doi: str | None,
    arxiv_id: str | None,
    first_author: str,
    year: int,
    evidence_level: str,
) -> RetrievalHit:
    return RetrievalHit(
        source_id=source_id,
        title=title,
        url=url,
        snippet=snippet,
        credibility_tier="peer_reviewed",
        doi=doi,
        arxiv_id=arxiv_id,
        first_author=first_author,
        year=year,
        evidence_level=evidence_level,
    )


def test_execute_retrieval_pipeline_policy_runtime_case_uses_real_evidence_path(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            reason_code="policy_keywords",
            scores={"policy": 5, "academic": 0, "industry": 0},
        )
    )
    live_policy_hits = [
        _policy_hit(
            source_id="policy_official_web_allowlist",
            title="Climate Order Mirror",
            url="https://www.gov.cn/zhengce/climate-order-mirror",
            snippet="Mirror notice without version metadata.",
            authority="State Council",
            publication_date="2026-04-01",
            effective_date="2026-05-01",
        ),
        _policy_hit(
            title="Climate Order",
            url="https://www.gov.cn/zhengce/climate-order",
            snippet="Official climate order with observed version metadata.",
            authority="State Council",
            jurisdiction="CN",
            publication_date="2026-04-01",
            effective_date="2026-05-01",
            version="2026-04 edition",
        ),
        _policy_hit(
            title="Emergency Water Use Notice",
            url="https://www.mee.gov.cn/policy/water-use-notice",
            snippet="Official notice with publication date but no version.",
            authority="Ministry of Ecology and Environment",
            publication_date="2026-02-10",
        ),
        _policy_hit(
            title="Industrial Emissions Guidance",
            url="https://www.mee.gov.cn/policy/emissions-guidance",
            snippet="Guidance with full policy metadata.",
            authority="Ministry of Ecology and Environment",
            jurisdiction="CN",
            publication_date="2026-01-15",
            version="2026-01 edition",
        ),
        _policy_hit(
            title="National Monitoring Circular",
            url="https://www.gov.cn/zhengce/monitoring-circular",
            snippet="Circular with effective date and observed version.",
            authority="State Council",
            jurisdiction="CN",
            effective_date="2026-03-20",
            version="2026-03 edition",
        ),
    ]

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        return _outcome(*live_policy_hits)

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="latest policy climate order",
            adapter_registry={},
        )
    )

    assert len(response.canonical_evidence) == 4
    assert len(response.results) == 4
    assert len(response.canonical_evidence) < len(live_policy_hits)
    assert [item.title for item in response.results] == [
        item.canonical_title for item in response.canonical_evidence
    ]
    assert "Climate Order Mirror" not in [item.title for item in response.results]

    climate_records = [
        item for item in response.canonical_evidence if item.canonical_title == "Climate Order"
    ]
    assert len(climate_records) == 1

    partial_policy = next(
        item
        for item in response.canonical_evidence
        if item.canonical_title == "Emergency Water Use Notice"
    )
    assert partial_policy.authority == "Ministry of Ecology and Environment"
    assert partial_policy.publication_date == "2026-02-10"
    assert partial_policy.version is None
    assert partial_policy.version_status == "version_missing"
    assert partial_policy.jurisdiction == "CN"
    assert partial_policy.jurisdiction_status == "jurisdiction_inferred"
    assert partial_policy.retained_slices
    assert response.evidence_clipped is False
    assert response.evidence_pruned is False


def test_execute_retrieval_pipeline_academic_runtime_case_merges_variants_on_real_path(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="academic",
            primary_route="academic",
            supplemental_route=None,
            reason_code="academic_keywords",
            scores={"policy": 0, "academic": 5, "industry": 0},
        )
    )
    published_hit = _academic_hit(
        source_id="academic_semantic_scholar",
        title="Grounded Search Evidence Packing",
        url="https://doi.org/10.5555/evidence.2026.10",
        snippet="Published canonical snippet.",
        doi="10.5555/evidence.2026.10",
        arxiv_id=None,
        first_author="Lin",
        year=2026,
        evidence_level="peer_reviewed",
    )
    preprint_hit = _academic_hit(
        source_id="academic_arxiv",
        title="Grounded Search Evidence Packing (working paper)",
        url="https://arxiv.org/abs/2604.12345",
        snippet="Preprint supporting snippet.",
        doi=None,
        arxiv_id="2604.12345",
        first_author="Lin",
        year=2026,
        evidence_level="preprint",
    )

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        return _outcome(preprint_hit, published_hit)

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="grounded search evidence packing paper",
            adapter_registry={},
        )
    )

    assert len(response.canonical_evidence) == 1
    assert len(response.results) == 1
    canonical = response.canonical_evidence[0]
    assert canonical.canonical_title == "Grounded Search Evidence Packing"
    assert canonical.canonical_url == "https://doi.org/10.5555/evidence.2026.10"
    assert canonical.evidence_level == "peer_reviewed"
    assert canonical.doi == "10.5555/evidence.2026.10"
    assert canonical.arxiv_id == "2604.12345"
    assert canonical.first_author == "Lin"
    assert canonical.year == 2026
    assert canonical.canonical_match_confidence == "heuristic"
    assert len(canonical.linked_variants) == 1
    assert canonical.linked_variants[0].variant_type == "preprint"
    assert canonical.linked_variants[0].canonical_match_confidence == "heuristic"
    assert [item.title for item in response.results] == [canonical.canonical_title]
    assert [item.snippet for item in response.results] == [
        canonical.retained_slices[0].text
    ]


def test_retrieve_response_exposes_additive_canonical_evidence_models() -> None:
    response = RetrieveResponse(
        route_label="mixed",
        primary_route="policy",
        supplemental_route="academic",
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        evidence_clipped=False,
        evidence_pruned=False,
        results=[],
        canonical_evidence=[
            {
                "evidence_id": "policy-canonical",
                "domain": "policy",
                "canonical_title": "Canonical policy bulletin",
                "canonical_url": "https://www.gov.cn/zhengce/canonical-policy",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Canonical policy retained slice.",
                        "source_record_id": "policy_official_registry",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            },
            {
                "evidence_id": "academic-canonical",
                "domain": "academic",
                "canonical_title": "Canonical published study",
                "canonical_url": "https://doi.org/10.1000/canonical-study",
                "route_role": "supplemental",
                "evidence_level": "peer_reviewed",
                "canonical_match_confidence": "strong_id",
                "doi": "10.1000/canonical-study",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "retained_slices": [
                    {
                        "text": "Canonical academic retained slice.",
                        "source_record_id": "academic_semantic_scholar",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [
                    {
                        "source_id": "academic_arxiv",
                        "title": "Canonical published study (preprint)",
                        "url": "https://arxiv.org/abs/2604.12345",
                        "variant_type": "preprint",
                        "canonical_match_confidence": "strong_id",
                        "doi": "10.1000/canonical-study",
                        "arxiv_id": "2604.12345",
                        "first_author": "Lin",
                        "year": 2026,
                    }
                ],
            },
        ],
    )

    assert response.canonical_evidence[0].authority == "State Council"
    assert response.canonical_evidence[0].version_status == "observed"
    assert response.canonical_evidence[1].doi == "10.1000/canonical-study"
    assert response.canonical_evidence[1].linked_variants[0].variant_type == "preprint"
    assert response.canonical_evidence[1].retained_slices[0].text == (
        "Canonical academic retained slice."
    )


def test_retrieve_response_budget_surface_only_exposes_clip_and_prune_signals() -> None:
    response = RetrieveResponse(
        route_label="policy",
        primary_route="policy",
        supplemental_route=None,
        browser_automation="disabled",
        status="success",
        failure_reason=None,
        gaps=[],
        evidence_clipped=True,
        evidence_pruned=True,
        results=[
            RetrieveResultItem(
                source_id="policy_official_registry",
                title="Canonical policy bulletin",
                url="https://www.gov.cn/zhengce/canonical-policy",
                snippet="Canonical policy retained slice.",
                credibility_tier="official_government",
            )
        ],
        canonical_evidence=[
            {
                "evidence_id": "policy-canonical",
                "domain": "policy",
                "canonical_title": "Canonical policy bulletin",
                "canonical_url": "https://www.gov.cn/zhengce/canonical-policy",
                "route_role": "primary",
                "authority": "State Council",
                "jurisdiction": "CN",
                "jurisdiction_status": "observed",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "version_status": "observed",
                "retained_slices": [
                    {
                        "text": "Canonical policy retained slice.",
                        "source_record_id": "policy_official_registry",
                        "source_span": "snippet",
                    }
                ],
                "linked_variants": [],
            }
        ],
    )

    payload = response.model_dump_json()
    assert '"evidence_clipped":true' in payload
    assert '"evidence_pruned":true' in payload
    assert "total_token_estimate" not in payload
    assert "token_budget" not in payload
    assert "token_estimate" not in payload


def test_retrieve_api_endpoint_routes_through_execute_retrieval_pipeline(monkeypatch) -> None:
    import skill.api.entry as api_entry

    observed: list[tuple[str, str | None]] = []

    async def _fake_pipeline(**kwargs: object) -> RetrieveResponse:
        plan = kwargs["plan"]
        observed.append((plan.primary_route, plan.supplemental_route))
        return RetrieveResponse(
            route_label=plan.route_label,
            primary_route=plan.primary_route,
            supplemental_route=plan.supplemental_route,
            browser_automation="disabled",
            status="success",
            failure_reason=None,
            gaps=[],
            evidence_clipped=True,
            results=[
                RetrieveResultItem(
                    source_id="policy_official_registry",
                    title="Official result",
                    url="https://www.gov.cn/official",
                    snippet="Grounded evidence",
                    credibility_tier="official_government",
                )
            ],
        )

    monkeypatch.setattr(
        api_entry,
        "execute_retrieval_pipeline",
        _fake_pipeline,
        raising=False,
    )

    client = TestClient(api_entry.app)
    response = client.post("/retrieve", json={"query": "latest policy bulletin"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["results"][0]["source_id"] == "policy_official_registry"
    assert payload["evidence_clipped"] is True
    assert "total_token_estimate" not in payload
    assert "token_budget" not in payload
    assert observed


def test_retrieve_response_enforces_outcome_invariants() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        RetrieveResponse(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            status="success",
            failure_reason="timeout",
            gaps=[],
            evidence_clipped=False,
            results=[],
        )

    with pytest.raises(ValueError, match="gaps"):
        RetrieveResponse(
            route_label="policy",
            primary_route="policy",
            supplemental_route=None,
            browser_automation="disabled",
            status="failure_gaps",
            failure_reason=None,
            gaps=[],
            evidence_clipped=False,
            results=[],
        )


def test_policy_adapters_emit_observed_authority_and_date_metadata() -> None:
    from skill.retrieval.adapters.policy_official_registry import search as registry_search
    from skill.retrieval.adapters.policy_official_web_allowlist import (
        search as allowlist_search,
    )

    registry_hits = asyncio.run(registry_search("official policy bulletin"))
    allowlist_hits = asyncio.run(allowlist_search("official policy bulletin"))
    combined_hits = [*registry_hits, *allowlist_hits]

    assert combined_hits
    assert all(
        getattr(hit, "authority", None)
        and (
            getattr(hit, "publication_date", None)
            or getattr(hit, "effective_date", None)
        )
        for hit in combined_hits
    )
    assert any(getattr(hit, "version", None) for hit in combined_hits)
    assert any(getattr(hit, "jurisdiction", None) for hit in combined_hits)


def test_academic_adapters_emit_observed_identifier_metadata() -> None:
    from skill.retrieval.adapters.academic_arxiv import search as arxiv_search
    from skill.retrieval.adapters.academic_semantic_scholar import (
        search as semantic_search,
    )

    semantic_hits = asyncio.run(semantic_search("evidence normalization"))
    arxiv_hits = asyncio.run(arxiv_search("evidence normalization"))

    assert semantic_hits
    assert arxiv_hits
    assert any(
        getattr(hit, "doi", None)
        and getattr(hit, "first_author", None)
        and getattr(hit, "year", None)
        and getattr(hit, "evidence_level", None)
        for hit in semantic_hits
    )
    assert any(
        getattr(hit, "arxiv_id", None)
        and getattr(hit, "first_author", None)
        and getattr(hit, "year", None)
        and getattr(hit, "evidence_level", None)
        for hit in arxiv_hits
    )


def test_normalize_hits_preserves_observed_metadata_from_mapping_payloads() -> None:
    from skill.retrieval.engine import _normalize_hits

    hits = _normalize_hits(
        raw_hits=[
            {
                "title": "Observed policy bulletin",
                "url": "https://www.gov.cn/zhengce/observed-bulletin",
                "snippet": "Observed metadata fixture",
                "authority": "State Council",
                "jurisdiction": "CN",
                "publication_date": "2026-04-01",
                "effective_date": "2026-05-01",
                "version": "2026-04 edition",
                "doi": "10.1000/example-doi",
                "arxiv_id": "2604.12345",
                "first_author": "Lin",
                "year": 2026,
                "evidence_level": "peer_reviewed",
            }
        ],
        source_id="policy_official_registry",
    )

    assert hits[0].authority == "State Council"
    assert hits[0].jurisdiction == "CN"
    assert hits[0].publication_date == "2026-04-01"
    assert hits[0].effective_date == "2026-05-01"
    assert hits[0].version == "2026-04 edition"
    assert hits[0].doi == "10.1000/example-doi"
    assert hits[0].arxiv_id == "2604.12345"
    assert hits[0].first_author == "Lin"
    assert hits[0].year == 2026
    assert hits[0].evidence_level == "peer_reviewed"
