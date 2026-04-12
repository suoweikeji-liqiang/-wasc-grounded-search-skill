"""Retrieval integration regressions for runtime orchestration and API wiring."""

from __future__ import annotations

import asyncio
import pytest

from fastapi.testclient import TestClient

from skill.api.schema import RetrieveResponse, RetrieveResultItem
from skill.evidence.models import CanonicalEvidence, EvidencePack, EvidenceSlice, LinkedVariant
from skill.evidence.normalize import build_raw_record
from skill.orchestrator.intent import ClassificationResult
from skill.orchestrator.retrieval_plan import build_retrieval_plan
from skill.retrieval.engine import RetrievalExecutionOutcome
from skill.retrieval.models import RetrievalHit


def _make_raw_record(
    *,
    source_id: str,
    title: str,
    url: str,
    snippet: str,
    route_role: str,
    credibility_tier: str | None,
    authority: str | None = None,
    jurisdiction: str | None = None,
    publication_date: str | None = None,
    effective_date: str | None = None,
    version: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    first_author: str | None = None,
    year: int | None = None,
    evidence_level: str | None = None,
):
    hit = RetrievalHit(
        source_id=source_id,
        title=title,
        url=url,
        snippet=snippet,
        credibility_tier=credibility_tier,
        authority=authority,
        jurisdiction=jurisdiction,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
        doi=doi,
        arxiv_id=arxiv_id,
        first_author=first_author,
        year=year,
        evidence_level=evidence_level,
    )
    return build_raw_record(hit=hit, route_role=route_role)


def _make_slice(
    *,
    source_record_id: str,
    text: str,
    score: float = 0.95,
    token_estimate: int = 4,
) -> EvidenceSlice:
    return EvidenceSlice(
        text=text,
        source_record_id=source_record_id,
        source_span="snippet",
        score=score,
        token_estimate=token_estimate,
    )


def _make_policy_canonical() -> CanonicalEvidence:
    raw_record = _make_raw_record(
        source_id="policy_official_registry",
        title="Canonical policy bulletin",
        url="https://www.gov.cn/zhengce/canonical-policy",
        snippet="Raw prioritized policy snippet that should stay internal.",
        route_role="primary",
        credibility_tier="official_government",
        authority="State Council",
        jurisdiction="CN",
        publication_date="2026-04-01",
        effective_date="2026-05-01",
        version="2026-04 edition",
    )
    return CanonicalEvidence(
        evidence_id="policy-canonical",
        domain="policy",
        canonical_title="Canonical policy bulletin",
        canonical_url="https://www.gov.cn/zhengce/canonical-policy",
        raw_records=(raw_record,),
        retained_slices=(
            _make_slice(
                source_record_id=raw_record.source_id,
                text="Canonical policy retained slice.",
            ),
        ),
        authority=raw_record.authority,
        jurisdiction=raw_record.jurisdiction,
        jurisdiction_status=raw_record.jurisdiction_status,
        publication_date=raw_record.publication_date,
        effective_date=raw_record.effective_date,
        version=raw_record.version,
        version_status=raw_record.version_status,
        route_role="primary",
        token_estimate=0,
    )


def _make_academic_canonical() -> CanonicalEvidence:
    raw_record = _make_raw_record(
        source_id="academic_semantic_scholar",
        title="Canonical published study",
        url="https://doi.org/10.1000/canonical-study",
        snippet="Raw prioritized academic snippet that should stay internal.",
        route_role="supplemental",
        credibility_tier="peer_reviewed_journal",
        doi="10.1000/canonical-study",
        arxiv_id="2604.12345",
        first_author="Lin",
        year=2026,
        evidence_level="peer_reviewed",
    )
    linked_variant = LinkedVariant(
        source_id="academic_arxiv",
        title="Canonical published study (preprint)",
        url="https://arxiv.org/abs/2604.12345",
        variant_type="preprint",
        canonical_match_confidence="strong_id",
        doi="10.1000/canonical-study",
        arxiv_id="2604.12345",
        first_author="Lin",
        year=2026,
    )
    return CanonicalEvidence(
        evidence_id="academic-canonical",
        domain="academic",
        canonical_title="Canonical published study",
        canonical_url="https://doi.org/10.1000/canonical-study",
        raw_records=(raw_record,),
        retained_slices=(
            _make_slice(
                source_record_id=raw_record.source_id,
                text="Canonical academic retained slice.",
            ),
        ),
        linked_variants=(linked_variant,),
        evidence_level="peer_reviewed",
        canonical_match_confidence="strong_id",
        doi=raw_record.doi,
        arxiv_id=raw_record.arxiv_id,
        first_author=raw_record.first_author,
        year=raw_record.year,
        route_role="supplemental",
        token_estimate=0,
    )


def test_execute_retrieval_pipeline_shapes_results_from_packed_canonical_evidence(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="academic",
            reason_code="explicit_cross_domain",
            scores={"policy": 5, "academic": 4, "industry": 0},
        )
    )
    prioritized_hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Raw prioritized academic hit",
            url="https://www.semanticscholar.org/paper/raw-hit",
            snippet="This raw prioritized snippet must not drive response shaping.",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Raw prioritized policy hit",
            url="https://www.gov.cn/zhengce/raw-hit",
            snippet="This raw prioritized policy snippet must not drive response shaping.",
        ),
    ]
    policy_canonical = _make_policy_canonical()
    academic_canonical = _make_academic_canonical()

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(prioritized_hits),
            source_results=(),
        )

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "prioritize_hits", lambda **_: prioritized_hits)
    monkeypatch.setattr(orchestrate, "normalize_hit_candidates", lambda **_: ["normalized"])
    monkeypatch.setattr(orchestrate, "collapse_evidence_records", lambda records: records)
    monkeypatch.setattr(orchestrate, "score_evidence_records", lambda records: records)
    monkeypatch.setattr(
        orchestrate,
        "build_evidence_pack",
        lambda *_, **__: EvidencePack(
            raw_records=(
                *policy_canonical.raw_records,
                *academic_canonical.raw_records,
            ),
            canonical_evidence=(policy_canonical, academic_canonical),
            clipped=True,
            pruned=True,
            total_token_estimate=999,
        ),
    )

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="policy and research synthesis",
            adapter_registry={},
        )
    )

    assert [item.title for item in response.results] == [
        "Canonical policy bulletin",
        "Canonical published study",
    ]
    assert [item.snippet for item in response.results] == [
        "Canonical policy retained slice.",
        "Canonical academic retained slice.",
    ]
    assert [item.source_id for item in response.results] == [
        "policy_official_registry",
        "academic_semantic_scholar",
    ]
    assert [item.evidence_id for item in response.canonical_evidence] == [
        "policy-canonical",
        "academic-canonical",
    ]
    assert response.evidence_clipped is True
    assert response.evidence_pruned is True


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


def test_execute_retrieval_pipeline_runs_post_priority_evidence_pipeline_in_order(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="academic",
            reason_code="explicit_cross_domain",
            scores={"policy": 5, "academic": 4, "industry": 0},
        )
    )
    raw_hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Supplemental paper",
            url="https://www.semanticscholar.org/paper/abc",
            snippet="Supplemental academic evidence",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Official registry page",
            url="https://www.mee.gov.cn/official",
            snippet="Official hit",
        ),
    ]
    events: list[str] = []

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        events.append("run_retrieval")
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(raw_hits),
            source_results=(),
        )

    def _fake_prioritize_hits(**kwargs: object) -> list[RetrievalHit]:
        events.append("prioritize_hits")
        assert kwargs["hits"] == raw_hits
        return [raw_hits[1], raw_hits[0]]

    def _fake_normalize_hit_candidates(**kwargs: object) -> list[str]:
        events.append("normalize_hit_candidates")
        assert kwargs["hits"] == [raw_hits[1], raw_hits[0]]
        assert kwargs["route_role_by_source"] == {
            "academic_semantic_scholar": "supplemental"
        }
        return ["normalized"]

    def _fake_collapse_evidence_records(records: list[str]) -> list[str]:
        events.append("collapse_evidence_records")
        assert records == ["normalized"]
        return ["canonical"]

    def _fake_score_evidence_records(records: list[str]) -> list[str]:
        events.append("score_evidence_records")
        assert records == ["canonical"]
        return ["scored"]

    def _fake_build_evidence_pack(
        records: list[str],
        *,
        token_budget: int,
        top_k: int,
        supplemental_min_items: int,
    ) -> EvidencePack:
        events.append("build_evidence_pack")
        assert records == ["scored"]
        assert token_budget > 0
        assert top_k > 0
        assert supplemental_min_items == 1
        return EvidencePack(
            raw_records=(),
            canonical_evidence=(),
            clipped=True,
            pruned=True,
            total_token_estimate=0,
        )

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "prioritize_hits", _fake_prioritize_hits)
    monkeypatch.setattr(orchestrate, "normalize_hit_candidates", _fake_normalize_hit_candidates)
    monkeypatch.setattr(orchestrate, "collapse_evidence_records", _fake_collapse_evidence_records)
    monkeypatch.setattr(orchestrate, "score_evidence_records", _fake_score_evidence_records)
    monkeypatch.setattr(orchestrate, "build_evidence_pack", _fake_build_evidence_pack)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="new policy release",
            adapter_registry={},
        )
    )

    assert events == [
        "run_retrieval",
        "prioritize_hits",
        "normalize_hit_candidates",
        "collapse_evidence_records",
        "score_evidence_records",
        "build_evidence_pack",
    ]
    assert [item.source_id for item in response.results] == [
        "policy_official_registry",
        "academic_semantic_scholar",
    ]
    assert response.evidence_clipped is True


def test_execute_retrieval_pipeline_mixed_route_preserves_primary_results_and_clip_flag(
    monkeypatch,
) -> None:
    import skill.retrieval.orchestrate as orchestrate

    plan = build_retrieval_plan(
        ClassificationResult(
            route_label="mixed",
            primary_route="policy",
            supplemental_route="academic",
            reason_code="explicit_cross_domain",
            scores={"policy": 5, "academic": 4, "industry": 0},
        )
    )
    raw_hits = [
        RetrievalHit(
            source_id="academic_semantic_scholar",
            title="Academic evidence",
            url="https://www.semanticscholar.org/paper/xyz",
            snippet="Supplemental source",
        ),
        RetrievalHit(
            source_id="policy_official_registry",
            title="Policy official evidence",
            url="https://www.gov.cn/zhengce/official",
            snippet="Primary-route source",
        ),
    ]

    async def _fake_run_retrieval(**_: object) -> RetrievalExecutionOutcome:
        return RetrievalExecutionOutcome(
            status="success",
            failure_reason=None,
            gaps=(),
            results=tuple(raw_hits),
            source_results=(),
        )

    def _fake_normalize_hit_candidates(**kwargs: object) -> list[object]:
        assert kwargs["route_role_by_source"] == {
            "academic_semantic_scholar": "supplemental"
        }
        return []

    def _fake_build_evidence_pack(
        records: list[object],
        *,
        token_budget: int,
        top_k: int,
        supplemental_min_items: int,
    ) -> EvidencePack:
        assert records == []
        assert token_budget > 0
        assert top_k > 0
        assert supplemental_min_items == 1
        return EvidencePack(
            raw_records=(),
            canonical_evidence=(),
            clipped=False,
            pruned=False,
            total_token_estimate=0,
        )

    monkeypatch.setattr(orchestrate, "run_retrieval", _fake_run_retrieval)
    monkeypatch.setattr(orchestrate, "normalize_hit_candidates", _fake_normalize_hit_candidates)
    monkeypatch.setattr(orchestrate, "collapse_evidence_records", lambda records: [])
    monkeypatch.setattr(orchestrate, "score_evidence_records", lambda records: [])
    monkeypatch.setattr(orchestrate, "build_evidence_pack", _fake_build_evidence_pack)

    response = asyncio.run(
        orchestrate.execute_retrieval_pipeline(
            plan=plan,
            query="policy and research synthesis",
            adapter_registry={},
        )
    )

    assert response.results
    assert response.results[0].source_id == "policy_official_registry"
    assert response.evidence_clipped is False


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
