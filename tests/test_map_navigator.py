import json
from unittest.mock import patch
from actions.map_navigator import (
    _get_live_location,
    map_navigator,
    TOOL,
)


def test_tool_declaration():
    assert TOOL["name"] == "map_navigator"
    assert "maps" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_telemetry_action():
    fake_loc = {
        "city": "Kathmandu",
        "region": "Bagmati",
        "country": "Nepal",
        "country_code": "NP",
        "latitude": 27.7172,
        "longitude": 85.3240,
        "timezone": "Asia/Kathmandu",
        "isp": "WorldLink",
    }
    with patch("actions.map_navigator._get_live_location", return_value=fake_loc):
        raw = map_navigator({"action": "telemetry", "open_browser": False})
        res = json.loads(raw)
        assert res["status"] == "success"
        assert res["action"] == "current_location"
        assert res["location"]["city"] == "Kathmandu"
        assert "Kathmandu" in res["summary"]


def test_show_map_action():
    with patch("webbrowser.open") as mock_open:
        raw = map_navigator({"action": "show_map", "location": "Tokyo", "open_browser": True})
        res = json.loads(raw)
        assert res["status"] == "success"
        assert res["action"] == "show_map"
        assert "Tokyo" in res["map_url"]
        mock_open.assert_called_once()


def test_directions_action():
    fake_loc = {"city": "Itahari"}
    fake_orig_geo = (26.66, 87.27, "Itahari, Nepal")
    fake_dest_geo = (27.71, 85.32, "Kathmandu, Nepal")
    fake_route_stats = {
        "distance_km": 365.6,
        "distance_miles": 227.2,
        "duration_minutes": 264,
        "duration_hours": 4.4,
    }

    with patch("actions.map_navigator._get_live_location", return_value=fake_loc), \
         patch("actions.map_navigator._geocode_location") as mock_geo, \
         patch("actions.map_navigator._calculate_driving_route", return_value=fake_route_stats), \
         patch("webbrowser.open") as mock_open:

        mock_geo.side_effect = [fake_orig_geo, fake_dest_geo]
        raw = map_navigator({
            "action": "directions",
            "origin": "Itahari",
            "destination": "Kathmandu",
            "open_browser": True
        })
        res = json.loads(raw)
        assert res["status"] == "success"
        assert res["action"] == "directions"
        assert res["route_stats"]["distance_km"] == 365.6
        assert "365.6 km" in res["summary"]
        assert "4.4 hours" in res["summary"]
        mock_open.assert_called_once()


def test_directions_missing_destination():
    raw = map_navigator({"action": "directions", "destination": ""})
    res = json.loads(raw)
    assert res["status"] == "error"
    assert "specify a destination" in res["message"]
