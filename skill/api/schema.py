"""API schemas for route request/response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
