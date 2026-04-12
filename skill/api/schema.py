"""API schemas for route and retrieval request/response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from skill.evidence.models import (
    CanonicalMatchConfidence,
    EvidenceLevel,
    PolicyJurisdictionStatus,
    PolicyVersionStatus,
    RouteRole,
)
from skill.retrieval.models import RetrievalFailureReason, RetrievalStatus


RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]


class RouteRequest(BaseModel):
    """Incoming route request payload."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=2000)

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("query must be non-empty after trimming")
        return normalized_value


class RouteResponse(BaseModel):
    """Observable routing metadata contract."""

    model_config = ConfigDict(extra="forbid")

    route_label: RouteLabel
    source_families: list[str]
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    browser_automation: Literal["disabled"]


class RetrieveRequest(BaseModel):
    """Incoming retrieval request payload."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=2000)

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("query must be non-empty after trimming")
        return normalized_value


class RetrieveResultItem(BaseModel):
    """Single retrieval evidence item."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    credibility_tier: str | None = None


class RetrieveRetainedSliceItem(BaseModel):
    """Observable retained evidence slice within a canonical evidence item."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_span: str | None = None


class RetrieveLinkedVariantItem(BaseModel):
    """Observable linked academic variant for a canonical evidence item."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    variant_type: str = Field(min_length=1)
    canonical_match_confidence: CanonicalMatchConfidence
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None


class RetrieveCanonicalEvidenceItem(BaseModel):
    """Bounded canonical evidence exposed for runtime observability."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    domain: ConcreteRoute
    canonical_title: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)
    route_role: RouteRole
    authority: str | None = None
    jurisdiction: str | None = None
    jurisdiction_status: PolicyJurisdictionStatus | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    version: str | None = None
    version_status: PolicyVersionStatus | None = None
    evidence_level: EvidenceLevel | None = None
    canonical_match_confidence: CanonicalMatchConfidence | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None
    retained_slices: list[RetrieveRetainedSliceItem] = Field(default_factory=list)
    linked_variants: list[RetrieveLinkedVariantItem] = Field(default_factory=list)


class RetrieveOutcome(BaseModel):
    """Structured retrieval outcome envelope."""

    model_config = ConfigDict(extra="forbid")

    status: RetrievalStatus
    failure_reason: RetrievalFailureReason | None = None
    gaps: list[str] = Field(default_factory=list)
    results: list[RetrieveResultItem] = Field(default_factory=list)

    @field_validator("failure_reason")
    @classmethod
    def validate_failure_reason_for_success(
        cls, value: RetrievalFailureReason | None, info: object
    ) -> RetrievalFailureReason | None:
        status = getattr(info, "data", {}).get("status")
        if status == "success" and value is not None:
            raise ValueError("failure_reason must be null when status='success'")
        return value

    @field_validator("gaps")
    @classmethod
    def validate_failure_gaps(
        cls, value: list[str], info: object
    ) -> list[str]:
        status = getattr(info, "data", {}).get("status")
        if status == "failure_gaps" and not value:
            raise ValueError("gaps must be non-empty when status='failure_gaps'")
        return value


class RetrieveResponse(RetrieveOutcome):
    """Retrieval response contract aligned with structured gap reporting."""

    route_label: RouteLabel
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    browser_automation: Literal["disabled"]
    canonical_evidence: list[RetrieveCanonicalEvidenceItem] = Field(default_factory=list)
    evidence_clipped: bool = False
    evidence_pruned: bool = False
