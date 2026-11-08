"""Tests for Smart Home IoT Bridge and Smart Home Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.iot_bridge import IoTBridge
from actions.smart_home import smart_home


@pytest.fixture
def temp_iot_bridge():
    with tempfile.TemporaryDirectory() as td:
        storage_path = Path(td) / "test_iot_devices.json"
        bridge = IoTBridge(storage_path=storage_path)
        yield bridge


def test_device_registration_and_listing(temp_iot_bridge):
    bridge = temp_iot_bridge
    dev1 = bridge.register_device("light.desk_lamp", name="Desk Lamp", domain="light")
    dev2 = bridge.register_device("switch.fan", name="Ceiling Fan", domain="switch")

    all_devs = bridge.list_devices()
    assert len(all_devs) == 2

    lights = bridge.list_devices(domain="light")
    assert len(lights) == 1
    assert lights[0].entity_id == "light.desk_lamp"


def test_device_control_lifecycle(temp_iot_bridge):
    bridge = temp_iot_bridge
    bridge.register_device("light.study", name="Study Light", domain="light", initial_state="off")

    # Turn on
    res = bridge.control_device("light.study", action="turn_on", attributes={"brightness": 80})
    assert res["state"] == "on"
    assert res["attributes"]["brightness"] == 80

    # Toggle
    res_toggle = bridge.control_device("light.study", action="toggle")
    assert res_toggle["state"] == "off"

    # Turn off
    res_off = bridge.control_device("light.study", action="turn_off")
    assert res_off["state"] == "off"


def test_storage_persistence(temp_iot_bridge):
    bridge = temp_iot_bridge
    bridge.register_device("climate.thermostat", name="Thermostat", domain="climate", initial_state="idle", attributes={"temperature": 21.5})

    # New bridge instance reading same file
    bridge2 = IoTBridge(storage_path=bridge.storage_path)
    dev = bridge2.get_device("climate.thermostat")
    assert dev is not None
    assert dev.name == "Thermostat"
    assert dev.attributes["temperature"] == 21.5


def test_smart_home_action_handler(temp_iot_bridge, monkeypatch):
    monkeypatch.setattr("actions.smart_home.get_iot_bridge", lambda: temp_iot_bridge)

    # Register
    reg_res = smart_home({
        "action": "register",
        "entity_id": "light.living_room",
        "name": "Living Room Ceiling Light",
        "domain": "light",
    })
    assert reg_res.status == "success"

    # Turn on
    on_res = smart_home({
        "action": "turn_on",
        "entity_id": "light.living_room",
        "brightness": 100,
    })
    assert on_res.status == "success"
    assert on_res.data["state"] == "on"
    assert on_res.data["attributes"]["brightness"] == 100

    # List
    list_res = smart_home({"action": "list"})
    assert list_res.status == "success"
    assert len(list_res.data["devices"]) == 1

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            smart_home({"action": "list"})
