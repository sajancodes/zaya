"""Display, Monitor & GPU Telemetry Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects hardware display metrics via pure Win32 user32 APIs:
native physical resolution, refresh rate, DPI scaling factor, color depth,
GPU display adapter identity, and multi-monitor virtual desktop geometry.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.execution_policy import require_owner


class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", wintypes.SHORT),
        ("dmPaperSize", wintypes.SHORT),
        ("dmPaperLength", wintypes.SHORT),
        ("dmPaperWidth", wintypes.SHORT),
        ("dmScale", wintypes.SHORT),
        ("dmCopies", wintypes.SHORT),
        ("dmDefaultSource", wintypes.SHORT),
        ("dmPrintQuality", wintypes.SHORT),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


def _get_display_adapters() -> List[Dict[str, Any]]:
    """Enumerate display adapters and active monitors."""
    if os.name != "nt":
        return [{"adapter": "Standard Display", "device": "\\\\.\\DISPLAY1", "primary": True, "attached": True}]

    adapters = []
    try:
        user32 = ctypes.windll.user32
        dd = _DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(_DISPLAY_DEVICEW)
        i = 0
        while user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            flags = dd.StateFlags
            attached = bool(flags & 1)
            primary = bool(flags & 4)
            adapters.append({
                "adapter": dd.DeviceString,
                "device": dd.DeviceName,
                "primary": primary,
                "attached": attached,
            })
            i += 1
    except Exception:
        pass
    return adapters


def _get_display_metrics() -> Dict[str, Any]:
    """Retrieve full display resolution, refresh rate, scaling, and geometry."""
    if os.name != "nt":
        return {
            "monitor_count": 1,
            "physical_width": 1920,
            "physical_height": 1080,
            "refresh_rate_hz": 60,
            "bits_per_pixel": 32,
            "logical_width": 1920,
            "logical_height": 1080,
            "dpi_scale_percent": 100,
            "virtual_desktop": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            "orientation": "Landscape",
            "primary_gpu": "Non-Windows Display",
        }

    user32 = ctypes.windll.user32

    # Logical metrics
    mon_count = user32.GetSystemMetrics(80) or 1  # SM_CMONITORS
    log_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    log_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    vx = user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
    vw = user32.GetSystemMetrics(78)    # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)    # SM_CYVIRTUALSCREEN

    # Physical metrics from EnumDisplaySettingsW
    phys_w = log_w
    phys_h = log_h
    refresh = 60
    bpp = 32
    orientation = "Landscape"

    try:
        dm = _DEVMODEW()
        dm.dmSize = ctypes.sizeof(_DEVMODEW)
        if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
            phys_w = int(dm.dmPelsWidth)
            phys_h = int(dm.dmPelsHeight)
            refresh = int(dm.dmDisplayFrequency)
            bpp = int(dm.dmBitsPerPel)
            if dm.dmOrientation == 1:
                orientation = "Portrait"
            elif dm.dmOrientation == 2:
                orientation = "Landscape (Flipped)"
            elif dm.dmOrientation == 3:
                orientation = "Portrait (Flipped)"
    except Exception:
        pass

    # DPI scale calculation
    dpi_scale = round((phys_w / max(1, log_w)) * 100.0) if log_w else 100

    # Adapter lookup
    adapters = _get_display_adapters()
    primary_gpu = "Standard Display Adapter"
    for a in adapters:
        if a.get("primary") and a.get("adapter"):
            primary_gpu = a["adapter"]
            break
    if primary_gpu == "Standard Display Adapter" and adapters:
        primary_gpu = adapters[0].get("adapter", primary_gpu)

    return {
        "monitor_count": mon_count,
        "physical_width": phys_w,
        "physical_height": phys_h,
        "refresh_rate_hz": refresh,
        "bits_per_pixel": bpp,
        "logical_width": log_w,
        "logical_height": log_h,
        "dpi_scale_percent": dpi_scale,
        "virtual_desktop": {"x": vx, "y": vy, "width": vw, "height": vh},
        "orientation": orientation,
        "primary_gpu": primary_gpu,
        "adapters": adapters,
    }


def display_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Display, Screen Resolution and GPU Monitor actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    metrics = _get_display_metrics()

    # 1. Overall Display & Monitor Summary
    if action in ("summary", "status", "resolution"):
        summary = (
            f"Display Telemetry: {metrics['physical_width']}x{metrics['physical_height']} @ {metrics['refresh_rate_hz']}Hz "
            f"({metrics['dpi_scale_percent']}% DPI scaling, {metrics['bits_per_pixel']}-bit color). "
            f"GPU: {metrics['primary_gpu']}. {metrics['monitor_count']} monitor(s) active."
        )
        return json.dumps({"status": "success", "summary": summary, "data": metrics}, indent=2)

    # 2. Attached Display Adapters & GPUs
    if action in ("adapters", "gpus", "devices"):
        adapters = metrics.get("adapters", [])
        attached = [a for a in adapters if a.get("attached")]
        summary = f"Found {len(attached)} attached display adapter(s): " + ", ".join(f"{a['adapter']} [{a['device']}]" for a in attached)
        return json.dumps({"status": "success", "summary": summary, "data": adapters}, indent=2)

    # 3. Geometry & Virtual Desktop
    if action in ("geometry", "monitors", "desktop"):
        vd = metrics["virtual_desktop"]
        summary = (
            f"Virtual Desktop: {vd['width']}x{vd['height']} at origin ({vd['x']}, {vd['y']}). "
            f"Primary logical workspace: {metrics['logical_width']}x{metrics['logical_height']} ({metrics['orientation']})."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "virtual_desktop": vd,
            "logical": {"width": metrics["logical_width"], "height": metrics["logical_height"]},
            "orientation": metrics["orientation"],
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, adapters, geometry."
    }, indent=2)


TOOL = {
    "name": "display_sentinel",
    "description": "Inspect physical screen resolution, refresh rate (Hz), DPI scaling factor, GPU display adapter, orientation, and multi-monitor virtual desktop geometry.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "adapters", "geometry"],
                "description": "Display operation to execute (default: 'summary').",
            },
        },
    },
    "handler": display_sentinel,
}
