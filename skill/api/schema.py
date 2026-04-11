"""API schemas for route and retrieval request/response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class RetrieveResponse(BaseModel):
    """Retrieval response contract aligned with structured gap reporting."""

    model_config = ConfigDict(extra="forbid")

    route_label: RouteLabel
    primary_route: ConcreteRoute
    supplemental_route: ConcreteRoute | None
    browser_automation: Literal["disabled"]
    status: RetrievalStatus
    failure_reason: RetrievalFailureReason | None = None
    gaps: list[str] = Field(default_factory=list)
    results: list[RetrieveResultItem] = Field(default_factory=list)
