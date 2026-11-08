"""Unit tests for Windows Bluetooth & Wireless Peripheral Sentinel.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.bluetooth_sentinel import (
    TOOL,
    _classify_device_type,
    _get_bluetooth_telemetry,
    bluetooth_sentinel,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_bluetooth_sentinel_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            bluetooth_sentinel({"action": "summary"})


def test_device_classification():
    assert _classify_device_type("Archana AirPods Pro - Find My") == "audio"
    assert _classify_device_type("Sony WH-1000XM4 Headset") == "audio"
    assert _classify_device_type("vivo Y17s") == "phone"
    assert _classify_device_type("Logitech MX Master 3S Mouse") == "mouse"
    assert _classify_device_type("Keychron K2 Keyboard") == "keyboard"
    assert _classify_device_type("Xbox Wireless Controller") == "gamepad"
    assert _classify_device_type("Generic Beacon XYZ") == "peripheral"


def test_bluetooth_sentinel_status_live():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = bluetooth_sentinel({"action": "status"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Bluetooth radio is" in res["summary"]


def test_bluetooth_sentinel_mocked():
    mock_data = {
        "adapter_present": True,
        "adapter_name": "Intel Wireless Bluetooth",
        "devices": [
            {"name": "AirPods Pro", "status": "OK", "connected": True, "type": "audio"},
            {"name": "vivo Y17s", "status": "Unknown", "connected": False, "type": "phone"},
        ],
        "connected_count": 1,
        "paired_count": 2,
    }
    with patch("actions.bluetooth_sentinel._get_bluetooth_telemetry", return_value=mock_data):
        with with_trust(TRUST_LOCAL_OWNER):
            # 1. Devices action
            res_raw = bluetooth_sentinel({"action": "devices"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert len(res["data"]) == 2

            # 2. Connected action
            conn_raw = bluetooth_sentinel({"action": "connected"})
            conn_res = json.loads(conn_raw)
            assert conn_res["status"] == "success"
            assert len(conn_res["data"]) == 1
            assert conn_res["data"][0]["name"] == "AirPods Pro"

            # 3. Summary action
            sum_raw = bluetooth_sentinel({"action": "summary"})
            sum_res = json.loads(sum_raw)
            assert "Bluetooth Sentinel: Radio is Active" in sum_res["summary"]
            assert "1 currently connected" in sum_res["summary"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "bluetooth_sentinel"
    assert "status" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "devices" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "connected" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_bluetooth():
    router = FastReflexRouter()
    
    intent, score = router.match("is bluetooth on")
    assert intent == "BLUETOOTH_STATUS_QUERY"
    assert score >= 0.88

    intent, score = router.match("bluetooth status")
    assert intent == "BLUETOOTH_STATUS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("BLUETOOTH_STATUS_QUERY")
    assert res.matched is True
    assert "Bluetooth is" in res.ack


def test_tool_router_maps_bluetooth_sentinel():
    router = ToolRouter()
    declarations = [
        {"name": "bluetooth_sentinel", "description": "inspect bluetooth adapter and connected wireless peripherals"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("check if my wireless bluetooth headphones are connected", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "bluetooth_sentinel" in names
