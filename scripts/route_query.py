"""CLI smoke utility for Phase 1 routing contract."""

from __future__ import annotations

import argparse
import json

from skill.orchestrator.intent import classify_query
from skill.orchestrator.planner import plan_route


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for one routing query."""

    parser = argparse.ArgumentParser(
        description="Classify and plan a route for one query using Phase 1 logic."
    )
    parser.add_argument("query", help="Query text to classify and route")
    return parser.parse_args()


def main() -> None:
    """Run routing flow and print schema-compatible JSON."""

    args = parse_args()
    classification = classify_query(args.query)
    response = plan_route(classification)
    print(response.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
