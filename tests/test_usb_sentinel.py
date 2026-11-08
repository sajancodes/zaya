"""Tests for Windows USB & Removable Device Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.usb_sentinel import (
    usb_sentinel,
    _categorize_usb_device,
    get_connected_usb_devices,
    get_removable_drives,
    get_usb_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_PNPUTIL_USB = """
Microsoft PnP Utility

Instance ID:        USB\\VID_1A2C&PID_4094&MI_00\\7&28866d02&0&0000
Device Description: USB Optical Mouse
Class Name:         HIDClass
Manufacturer Name:  (Standard system devices)
Status:             Started
Driver Name:        input.inf

Instance ID:        USB\\VID_13D3&PID_54B6&MI_00\\7&2d27fd89&0&0000
Device Description: Integrated Camera
Class Name:         Camera
Manufacturer Name:  Sonix
Status:             Started
Driver Name:        oem12.inf

Instance ID:        PCI\\VEN_10DE&DEV_28E1\\4&916989f&0&0009
Device Description: NVIDIA GeForce RTX 4050 Laptop GPU
Class Name:         Display
Manufacturer Name:  NVIDIA
Status:             Started
Driver Name:        oem13.inf

Instance ID:        USB\\ROOT_HUB30\\5&833cf9d&0&0
Device Description: USB Root Hub (USB 3.0)
Class Name:         USB
Manufacturer Name:  (Standard USB HUBs)
Status:             Started
Driver Name:        usbhub3.inf
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        usb_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "usb_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_categorize_usb_device():
    assert _categorize_usb_device("HIDClass", "USB Keyboard") == "Input / Peripheral"
    assert _categorize_usb_device("Camera", "Webcam HD") == "Camera / Imaging"
    assert _categorize_usb_device("MEDIA", "USB Headset") == "Audio / Media"
    assert _categorize_usb_device("DiskDrive", "SanDisk Ultra USB Device") == "Storage"
    assert _categorize_usb_device("USB", "USB Root Hub") == "Host Controller / Hub"
    assert _categorize_usb_device("Other", "Custom Dongle") == "General USB Device"


@patch("subprocess.run")
def test_get_connected_usb_devices(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_PNPUTIL_USB)

    # Exclude internal hubs
    devices = get_connected_usb_devices(include_internal_hubs=False)
    assert len(devices) == 2
    assert devices[0]["device_description"] == "USB Optical Mouse"
    assert devices[0]["category"] == "Input / Peripheral"
    assert devices[1]["device_description"] == "Integrated Camera"
    assert devices[1]["category"] == "Camera / Imaging"

    # Include internal hubs
    all_devices = get_connected_usb_devices(include_internal_hubs=True)
    assert len(all_devices) == 3


@patch("subprocess.run")
def test_get_connected_usb_devices_error(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
    devices = get_connected_usb_devices()
    assert devices == []


@patch("psutil.disk_usage")
@patch("psutil.disk_partitions")
def test_get_removable_drives(mock_parts, mock_usage):
    mock_part_fixed = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    mock_part_usb = MagicMock(device="E:\\", mountpoint="E:\\", fstype="FAT32", opts="rw,removable")
    mock_parts.return_value = [mock_part_fixed, mock_part_usb]

    mock_usage.return_value = MagicMock(
        total=32 * (1024**3),
        used=8 * (1024**3),
        free=24 * (1024**3),
        percent=25.0,
    )

    drives = get_removable_drives()
    assert len(drives) == 1
    assert drives[0]["mountpoint"] == "E:\\"
    assert drives[0]["filesystem"] == "FAT32"
    assert drives[0]["total_gb"] == 32.0
    assert drives[0]["free_gb"] == 24.0


@patch("actions.usb_sentinel.get_removable_drives")
@patch("actions.usb_sentinel.get_connected_usb_devices")
def test_get_usb_summary(mock_devs, mock_drives):
    mock_devs.return_value = [
        {"device_description": "USB Mouse", "category": "Input / Peripheral"},
        {"device_description": "USB Camera", "category": "Camera / Imaging"},
    ]
    mock_drives.return_value = [{"mountpoint": "E:\\"}]

    summary = get_usb_summary()
    assert summary["connected_usb_devices_count"] == 2
    assert summary["removable_drives_count"] == 1
    assert "USB Mouse" in summary["peripherals"]
    assert "USB Camera" in summary["peripherals"]


def test_usb_sentinel_actions():
    res_raw = usb_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    dev_raw = usb_sentinel({"action": "devices"})
    dev = json.loads(dev_raw)
    assert dev["status"] == "success"
    assert "devices" in dev

    drv_raw = usb_sentinel({"action": "drives"})
    drv = json.loads(drv_raw)
    assert drv["status"] == "success"
    assert "drives" in drv

    err_raw = usb_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_usb_devices():
    router = FastReflexRouter()
    intent, score = router.match("what usb devices are plugged in")
    assert intent == "USB_DEVICES_QUERY"
    assert score >= 0.88

    res = router.execute_intent("USB_DEVICES_QUERY")
    assert res.matched is True
    assert "connected USB devices" in res.ack
