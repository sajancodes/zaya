"""Tests for Flight Finder and Air Travel Intelligence.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.flight_finder import FlightFinder, get_flight_finder
from actions.flight_search import flight_search


class TestFlightFinder:
    def test_iata_code_resolution(self):
        finder = FlightFinder()
        assert finder.resolve_iata("Kathmandu") == "KTM"
        assert finder.resolve_iata("KTM") == "KTM"
        assert finder.resolve_iata("New York") == "JFK"
        assert finder.resolve_iata("London") == "LHR"
        assert finder.resolve_iata("Dubai") == "DXB"
        assert finder.resolve_iata("Tokyo") == "HND"

    def test_search_flights_valid_route(self):
        finder = FlightFinder()
        offers = finder.search_flights(
            origin="Kathmandu",
            destination="Dubai",
            departure_date="2026-12-01",
            passengers=1,
            cabin_class="economy",
        )
        assert len(offers) >= 1
        cheapest = offers[0]
        assert cheapest.origin == "KTM"
        assert cheapest.destination == "DXB"
        assert cheapest.price_usd > 0
        assert cheapest.airline != ""

    def test_search_flights_cabin_multiplier(self):
        finder = FlightFinder()
        econ = finder.search_flights("JFK", "LHR", cabin_class="economy")
        biz = finder.search_flights("JFK", "LHR", cabin_class="business")
        assert biz[0].price_usd > econ[0].price_usd

    def test_search_same_origin_and_dest_returns_empty(self):
        finder = FlightFinder()
        offers = finder.search_flights("KTM", "KTM")
        assert offers == []

    def test_format_summary(self):
        finder = FlightFinder()
        offers = finder.search_flights("KTM", "DOH")
        summary = finder.format_summary(offers, "Kathmandu", "Doha")
        assert "flight options from KTM to DOH" in summary
        assert "Best Price:" in summary


class TestFlightSearchAction:
    def test_action_success(self):
        res = flight_search({"origin": "Kathmandu", "destination": "London", "passengers": 1})
        assert res.status == "success"
        assert "flight options" in res.summary
        assert res.data["count"] > 0

    def test_action_missing_params(self):
        res = flight_search({"origin": "Kathmandu"})
        assert res.status == "failed"
        assert "specify both" in res.summary
