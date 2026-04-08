"""Planning utilities mapping classification to route response."""

from __future__ import annotations

from skill.api.schema import RouteResponse
from skill.config.routes import ROUTE_SOURCE_FAMILIES
from skill.orchestrator.intent import ClassificationResult


def _ordered_unique(values: list[str]) -> list[str]:
    unique_values: dict[str, None] = {}
    for value in values:
        if value not in unique_values:
            unique_values[value] = None
    return list(unique_values.keys())


def plan_route(result: ClassificationResult) -> RouteResponse:
    primary_families = list(ROUTE_SOURCE_FAMILIES[result.primary_route])

    if result.route_label == "mixed" and result.supplemental_route is not None:
        supplemental_families = list(ROUTE_SOURCE_FAMILIES[result.supplemental_route])
        source_families = _ordered_unique(primary_families + supplemental_families)
    else:
        source_families = primary_families

    return RouteResponse(
        route_label=result.route_label,
        source_families=source_families,
        primary_route=result.primary_route,
        supplemental_route=result.supplemental_route,
        browser_automation="disabled",
    )
