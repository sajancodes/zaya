"""Global Maps, Live Location Telemetry & Navigation Routing Engine.

Provides physical location telemetry, interactive map viewing, and
road route distance/duration calculation with Google Maps navigation dispatch.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import webbrowser
from typing import Any, Dict, Optional, Tuple


def _get_live_location() -> Optional[Dict[str, Any]]:
    """Fetches user physical location telemetry via IP geolocation."""
    url = "http://ip-api.com/json/"
    req = urllib.request.Request(url, headers={"User-Agent": "ZayaAssistant/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                return {
                    "city": data.get("city", "Unknown"),
                    "region": data.get("regionName", ""),
                    "country": data.get("country", ""),
                    "country_code": data.get("countryCode", ""),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "timezone": data.get("timezone", ""),
                    "isp": data.get("isp", ""),
                }
    except Exception:
        pass
    return None


def _geocode_location(query: str) -> Optional[Tuple[float, float, str]]:
    """Resolves an address or city to (latitude, longitude, display_name)."""
    encoded = urllib.parse.quote(query.strip())
    url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "ZayaAssistant/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                first = data[0]
                lat = float(first["lat"])
                lon = float(first["lon"])
                display = first.get("display_name", query)
                return lat, lon, display
    except Exception:
        pass
    return None


def _calculate_driving_route(lon1: float, lat1: float, lon2: float, lat2: float) -> Optional[Dict[str, float]]:
    """Calculates road distance and driving duration via public OSRM."""
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    req = urllib.request.Request(url, headers={"User-Agent": "ZayaAssistant/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            routes = data.get("routes", [])
            if routes:
                route = routes[0]
                dist_km = route.get("distance", 0.0) / 1000.0
                dur_mins = route.get("duration", 0.0) / 60.0
                return {
                    "distance_km": round(dist_km, 1),
                    "distance_miles": round(dist_km * 0.621371, 1),
                    "duration_minutes": round(dur_mins),
                    "duration_hours": round(dur_mins / 60.0, 1),
                }
    except Exception:
        pass
    return None


def map_navigator(parameters: dict, **_kwargs) -> str:
    """Handles location queries, map display, and route navigation."""
    action = str(parameters.get("action") or "telemetry").lower().strip()
    query = str(parameters.get("query") or parameters.get("location") or "").strip()
    origin = str(parameters.get("origin") or "").strip()
    destination = str(parameters.get("destination") or query or "").strip()
    open_browser = parameters.get("open_browser", True)

    # 1. Telemetry / Current Location
    if action in ("telemetry", "current_location", "where_am_i", "live_location"):
        loc = _get_live_location()
        if not loc:
            return json.dumps({
                "status": "error",
                "message": "Unable to determine current physical location."
            }, indent=2)

        summary = (
            f"You are currently in {loc['city']}, {loc['country']} "
            f"({loc['timezone']} timezone, coordinates {loc['latitude']:.2f}°, {loc['longitude']:.2f}°)."
        )

        if open_browser and parameters.get("open_map"):
            map_url = f"https://www.google.com/maps/search/?api=1&query={loc['latitude']},{loc['longitude']}"
            webbrowser.open(map_url)

        return json.dumps({
            "status": "success",
            "action": "current_location",
            "location": loc,
            "summary": summary
        }, indent=2)

    # 2. Open / Show Map for a location
    if action in ("show_map", "open_map", "search"):
        target = query or destination
        if not target:
            return json.dumps({
                "status": "error",
                "message": "Please specify a location or city to view on the map."
            }, indent=2)

        map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(target)}"
        if open_browser:
            webbrowser.open(map_url)

        return json.dumps({
            "status": "success",
            "action": "show_map",
            "location": target,
            "map_url": map_url,
            "summary": f"I have opened the map for {target} on your display."
        }, indent=2)

    # 3. Route & Driving Directions
    if action in ("directions", "route", "navigation", "distance"):
        if not destination:
            return json.dumps({
                "status": "error",
                "message": "Please specify a destination for driving directions."
            }, indent=2)

        # Default origin to current live city if not specified
        if not origin:
            loc = _get_live_location()
            origin = loc.get("city") if loc else ""

        if not origin:
            return json.dumps({
                "status": "error",
                "message": "Please specify a starting location (origin) for directions."
            }, indent=2)

        # Geocode both endpoints
        orig_geo = _geocode_location(origin)
        dest_geo = _geocode_location(destination)

        route_stats = None
        if orig_geo and dest_geo:
            route_stats = _calculate_driving_route(orig_geo[1], orig_geo[0], dest_geo[1], dest_geo[0])

        nav_url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}"
        if open_browser:
            webbrowser.open(nav_url)

        if route_stats:
            summary = (
                f"The driving distance from {origin} to {destination} is approximately "
                f"{route_stats['distance_km']} km ({route_stats['distance_miles']} miles), "
                f"with an estimated driving time of {route_stats['duration_hours']} hours "
                f"({route_stats['duration_minutes']} minutes). I have opened the full navigation route on your display."
            )
        else:
            summary = f"I have opened the navigation route from {origin} to {destination} on your display."

        return json.dumps({
            "status": "success",
            "action": "directions",
            "origin": origin,
            "destination": destination,
            "route_stats": route_stats,
            "navigation_url": nav_url,
            "summary": summary
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unsupported action '{action}'. Choose from: telemetry, show_map, directions."
    }, indent=2)


TOOL = {
    "name": "map_navigator",
    "description": (
        "Global interactive maps, real-time live location telemetry, and turn-by-turn road driving directions. "
        "Allows looking up current physical location, displaying map for any city/landmark, and calculating travel routes."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'telemetry' for current live location; 'show_map' to display a map of any city or place; 'directions' for driving route between origin and destination.",
                "enum": ["telemetry", "show_map", "directions"]
            },
            "location": {
                "type": "STRING",
                "description": "City, landmark, or address to display on the map (used with 'show_map')."
            },
            "origin": {
                "type": "STRING",
                "description": "Starting location for driving directions. If omitted, defaults to the user's current city."
            },
            "destination": {
                "type": "STRING",
                "description": "Destination city or landmark for driving directions (used with 'directions')."
            }
        },
        "required": ["action"]
    },
    "handler": map_navigator,
}
