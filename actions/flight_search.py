"""Flight Search Action for Zaya air travel discovery.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from dataclasses import asdict
from core.flight_finder import get_flight_finder
from core.tool_result import ToolResult


def flight_search(parameters: dict, **_kwargs) -> ToolResult:
    """Find airline flights and route options."""
    origin = parameters.get("origin", "").strip()
    destination = parameters.get("destination", "").strip()

    if not origin or not destination:
        return ToolResult("failed", "Please specify both origin and destination cities or airport codes.")

    finder = get_flight_finder()
    date_str = parameters.get("date")
    return_date = parameters.get("return_date")
    passengers = int(parameters.get("passengers", 1))
    cabin = parameters.get("cabin_class", "economy")

    offers = finder.search_flights(
        origin=origin,
        destination=destination,
        departure_date=date_str,
        return_date=return_date,
        passengers=passengers,
        cabin_class=cabin,
    )

    summary = finder.format_summary(offers, origin, destination)
    return ToolResult(
        "success" if offers else "partial",
        summary,
        data={
            "origin": finder.resolve_iata(origin),
            "destination": finder.resolve_iata(destination),
            "count": len(offers),
            "flights": [asdict(o) for o in offers],
        },
    )


TOOL = {
    "name": "flight_search",
    "description": "Search commercial airline flights between cities or airport codes with prices, durations, airlines, and stops.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "origin": {"type": "STRING", "description": "Departure city or 3-letter IATA code (e.g. 'Kathmandu', 'JFK', 'London')."},
            "destination": {"type": "STRING", "description": "Arrival city or 3-letter IATA code (e.g. 'Dubai', 'Tokyo', 'LHR')."},
            "date": {"type": "STRING", "description": "Optional departure date in YYYY-MM-DD format."},
            "return_date": {"type": "STRING", "description": "Optional return date for round trips."},
            "passengers": {"type": "INTEGER", "description": "Number of passengers (default 1)."},
            "cabin_class": {
                "type": "STRING",
                "enum": ["economy", "premium", "business", "first"],
                "description": "Travel class (default 'economy').",
            },
        },
        "required": ["origin", "destination"],
    },
    "handler": flight_search,
}
