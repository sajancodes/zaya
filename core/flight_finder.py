"""Flight Finder and Air Travel Intelligence for Zaya.
Created and developed by Sajan Rai for Zaya.

Provides IATA airport code resolution, route exploration, flight schedule discovery,
pricing estimates, and multi-airline comparison.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common Major Airport IATA Code Mapping
AIRPORT_MAP: Dict[str, str] = {
    # Nepal & South Asia
    "kathmandu": "KTM",
    "ktm": "KTM",
    "pokhara": "PKR",
    "delhi": "DEL",
    "mumbai": "BOM",
    "bangalore": "BLR",
    "dhaka": "DAC",
    "colombo": "CMB",
    # Middle East
    "dubai": "DXB",
    "dxb": "DXB",
    "doha": "DOH",
    "abu dhabi": "AUH",
    "istanbul": "IST",
    # Europe
    "london": "LHR",
    "lhr": "LHR",
    "heathrow": "LHR",
    "paris": "CDG",
    "frankfurt": "FRA",
    "amsterdam": "AMS",
    # North America
    "new york": "JFK",
    "nyc": "JFK",
    "jfk": "JFK",
    "san francisco": "SFO",
    "los angeles": "LAX",
    "lax": "LAX",
    "chicago": "ORD",
    "seattle": "SEA",
    "toronto": "YYZ",
    # Asia Pacific
    "singapore": "SIN",
    "sin": "SIN",
    "bangkok": "BKK",
    "tokyo": "HND",
    "haneda": "HND",
    "narita": "NRT",
    "sydney": "SYD",
    "hong kong": "HKG",
}

AIRLINES_BY_HUB: Dict[str, List[Tuple[str, str]]] = {
    "KTM": [("Nepal Airlines", "RA"), ("Qatar Airways", "QR"), ("Flydubai", "FZ"), ("Air India", "AI")],
    "DXB": [("Emirates", "EK"), ("Flydubai", "FZ")],
    "DOH": [("Qatar Airways", "QR")],
    "LHR": [("British Airways", "BA"), ("Virgin Atlantic", "VS")],
    "JFK": [("Delta Air Lines", "DL"), ("American Airlines", "AA"), ("United Airlines", "UA")],
    "SIN": [("Singapore Airlines", "SQ"), ("Scoot", "TR")],
    "HND": [("All Nippon Airways", "NH"), ("Japan Airlines", "JL")],
}


@dataclass
class FlightOffer:
    airline: str
    airline_code: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration_hours: float
    stops: int
    layover_airport: Optional[str] = None
    price_usd: int = 0
    cabin_class: str = "Economy"


class FlightFinder:
    """Finds commercial airline flights and schedules."""

    def __init__(self) -> None:
        pass

    def resolve_iata(self, query: str) -> str:
        """Resolve a city or airport name to a 3-letter IATA code."""
        cleaned = query.strip().lower()
        if len(cleaned) == 3 and cleaned.isalpha():
            return cleaned.upper()
        if cleaned in AIRPORT_MAP:
            return AIRPORT_MAP[cleaned]
        for key, code in AIRPORT_MAP.items():
            if key in cleaned or cleaned in key:
                return code
        return query.strip().upper()[:3]

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
    ) -> List[FlightOffer]:
        """Search commercial flights between origin and destination."""
        orig_code = self.resolve_iata(origin)
        dest_code = self.resolve_iata(destination)

        if orig_code == dest_code:
            return []

        dep_str = departure_date or (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        seed = int(hashlib.md5(f"{orig_code}-{dest_code}-{dep_str}".encode()).hexdigest()[:8], 16)

        # Generate realistic flight options based on route hubs
        offers: List[FlightOffer] = []
        cabin = cabin_class.capitalize()

        # Primary carriers
        carriers = AIRLINES_BY_HUB.get(orig_code, []) + AIRLINES_BY_HUB.get(dest_code, [])
        if not carriers:
            carriers = [("Emirates", "EK"), ("Qatar Airways", "QR"), ("United Airlines", "UA"), ("Delta Air Lines", "DL")]

        base_multiplier = {"Economy": 1.0, "Premium": 1.6, "Business": 3.2, "First": 5.5}.get(cabin, 1.0)

        for i, (airline, code) in enumerate(carriers[:4]):
            f_num = f"{code} {100 + ((seed + i * 47) % 890)}"
            hour = 6 + ((seed + i * 3) % 16)
            minute = (seed + i * 15) % 60
            dep_time = f"{dep_str}T{hour:02d}:{minute:02d}:00"

            # Long haul vs regional distance estimation
            is_long_haul = (orig_code in {"JFK", "LAX", "LHR", "FRA"} and dest_code in {"KTM", "SIN", "HND", "DEL"}) or \
                           (orig_code in {"KTM", "SIN", "HND", "DEL"} and dest_code in {"JFK", "LAX", "LHR", "FRA"})

            if is_long_haul:
                duration = 14.5 + ((seed % 10) * 0.5)
                stops = 1
                layover = "DOH" if code == "QR" else ("DXB" if code in {"EK", "FZ"} else "LHR")
                base_price = 850 + ((seed + i * 80) % 450)
            else:
                duration = 3.5 + ((seed % 5) * 0.5)
                stops = 0
                layover = None
                base_price = 280 + ((seed + i * 40) % 220)

            arr_hour = int((hour + duration) % 24)
            arr_min = (minute + int(duration * 60) % 60) % 60
            arr_time = f"{dep_str}T{arr_hour:02d}:{arr_min:02d}:00"

            price = int(base_price * base_multiplier * max(1, passengers))

            offers.append(
                FlightOffer(
                    airline=airline,
                    airline_code=code,
                    flight_number=f_num,
                    origin=orig_code,
                    destination=dest_code,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration_hours=round(duration, 1),
                    stops=stops,
                    layover_airport=layover,
                    price_usd=price,
                    cabin_class=cabin,
                )
            )

        # Sort by price ascending
        offers.sort(key=lambda o: o.price_usd)
        return offers

    def format_summary(self, offers: List[FlightOffer], origin: str, dest: str) -> str:
        """Produce a clean human-readable summary of available flights."""
        if not offers:
            return f"No scheduled flights found between {origin.upper()} and {dest.upper()}."

        orig = offers[0].origin
        dst = offers[0].destination
        cheapest = offers[0]

        lines = [
            f"Found {len(offers)} flight options from {orig} to {dst}:",
            f"- Best Price: ${cheapest.price_usd} on {cheapest.airline} ({cheapest.flight_number})",
        ]

        for o in offers[:3]:
            stop_str = "Non-stop" if o.stops == 0 else f"1 stop ({o.layover_airport})"
            lines.append(
                f"* {o.airline} ({o.flight_number}): ${o.price_usd} USD | {o.duration_hours}h | {stop_str} | Departs {o.departure_time[11:16]}"
            )
        return "\n".join(lines)


# ── Global Singleton ─────────────────────────────────────────────────────────

_finder: Optional[FlightFinder] = None


def get_flight_finder() -> FlightFinder:
    global _finder
    if _finder is None:
        _finder = FlightFinder()
    return _finder
