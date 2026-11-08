"""Tests for Hardware Device & System Driver Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.driver_sentinel import (
    driver_sentinel,
    _parse_pnputil_blocks,
    get_problem_devices,
    get_installed_drivers,
    get_devices_by_class,
    get_hardware_health_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_DRIVERS_TEXT = """
Microsoft PnP Utility

Published Name:     oem13.inf
Original Name:      nvlt.inf
Provider Name:      NVIDIA
Class Name:         Display
Class GUID:         {4d36e968-e325-11ce-bfc1-08002be10318}
Driver Version:     12/19/2025 32.0.15.9166
Signer Name:        Microsoft Windows Hardware Compatibility Publisher

Published Name:     oem25.inf
Original Name:      rt68cx21x64.inf
Provider Name:      Realtek
Class Name:         Net
Class GUID:         {4d36e972-e325-11ce-bfc1-08002be10318}
Driver Version:     09/19/2025 1168.27.50.919
Signer Name:        Microsoft Windows Hardware Compatibility Publisher
"""

_MOCK_PROBLEM_DEVICE_TEXT = """
Microsoft PnP Utility

Instance ID:        PCI\\VEN_10EC&DEV_5229\\0
Device Description: Realtek PCIE CardReader
Class Name:         MTD
Class GUID:         {4d36e970-e325-11ce-bfc1-08002be10318}
Manufacturer Name:  Realtek
Status:             Error
Problem Code:       10
"""

_MOCK_DISPLAY_DEVICE_TEXT = """
Microsoft PnP Utility

Instance ID:        PCI\\VEN_10DE&DEV_28E1\\4&916989f&0&0009
Device Description: NVIDIA GeForce RTX 4050 Laptop GPU
Class Name:         Display
Manufacturer Name:  NVIDIA
Status:             Started
Driver Name:        oem13.inf
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        driver_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "driver_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_parse_pnputil_blocks():
    parsed = _parse_pnputil_blocks(_MOCK_DRIVERS_TEXT)
    assert len(parsed) == 2
    assert parsed[0]["published_name"] == "oem13.inf"
    assert parsed[0]["provider_name"] == "NVIDIA"
    assert parsed[0]["class_name"] == "Display"
    assert parsed[1]["published_name"] == "oem25.inf"
    assert parsed[1]["provider_name"] == "Realtek"


@patch("subprocess.run")
def test_get_problem_devices_clean(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Microsoft PnP Utility\n\nNo devices were found on the system.")
    problems = get_problem_devices()
    assert problems == []


@patch("subprocess.run")
def test_get_problem_devices_with_fault(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_PROBLEM_DEVICE_TEXT)
    problems = get_problem_devices()
    assert len(problems) == 1
    assert problems[0]["device_description"] == "Realtek PCIE CardReader"
    assert problems[0]["problem_code"] == "10"


@patch("subprocess.run")
def test_get_installed_drivers(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_DRIVERS_TEXT)
    drivers = get_installed_drivers(limit=10)
    assert len(drivers) == 2
    assert drivers[0]["provider_name"] == "NVIDIA"


@patch("subprocess.run")
def test_get_devices_by_class(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_DISPLAY_DEVICE_TEXT)
    devices = get_devices_by_class("Display")
    assert len(devices) == 1
    assert devices[0]["device_description"] == "NVIDIA GeForce RTX 4050 Laptop GPU"
    assert devices[0]["status"] == "Started"


@patch("actions.driver_sentinel.get_devices_by_class")
@patch("actions.driver_sentinel.get_installed_drivers")
@patch("actions.driver_sentinel.get_problem_devices")
def test_get_hardware_health_summary(mock_prob, mock_drv, mock_cls):
    mock_prob.return_value = []
    mock_drv.return_value = [
        {"provider_name": "NVIDIA"},
        {"provider_name": "NVIDIA"},
        {"provider_name": "Realtek"},
    ]
    mock_cls.side_effect = lambda c: [
        {"device_description": "NVIDIA GeForce RTX 4050 Laptop GPU"}
    ] if c == "Display" else [
        {"device_description": "Realtek PCIe GbE Family Controller"}
    ]

    summary = get_hardware_health_summary()
    assert "Healthy" in summary["hardware_health"]
    assert summary["problem_device_count"] == 0
    assert summary["total_oem_drivers"] == 3
    assert summary["primary_gpu"] == "NVIDIA GeForce RTX 4050 Laptop GPU"


def test_driver_sentinel_actions():
    res_raw = driver_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    prob_raw = driver_sentinel({"action": "problems"})
    prob = json.loads(prob_raw)
    assert prob["status"] == "success"
    assert "problems" in prob

    err_raw = driver_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_hardware_devices():
    router = FastReflexRouter()
    intent, score = router.match("check hardware devices")
    assert intent == "HARDWARE_DEVICES_QUERY"
    assert score >= 0.88

    res = router.execute_intent("HARDWARE_DEVICES_QUERY")
    assert res.matched is True
    assert "Hardware Health:" in res.ack
