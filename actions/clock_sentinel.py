"""Windows Timezone, NTP Clock & Time Synchronization Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects system timezone, dynamic bias, UTC offsets, local vs UTC time,
and configured Windows NTP time synchronization servers via Win32 kernel32 and registry.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import datetime
import json
import os
import time
from typing import Any, Dict, List, Optional
import winreg

from core.execution_policy import require_owner


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class _DYNAMIC_TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Bias", ctypes.c_long),
        ("StandardName", wintypes.WCHAR * 32),
        ("StandardDate", _SYSTEMTIME),
        ("StandardBias", ctypes.c_long),
        ("DaylightName", wintypes.WCHAR * 32),
        ("DaylightDate", _SYSTEMTIME),
        ("DaylightBias", ctypes.c_long),
        ("TimeZoneKeyName", wintypes.WCHAR * 128),
        ("DynamicDaylightTimeDisabled", wintypes.BOOLEAN),
    ]


def get_system_timezone_info() -> Dict[str, Any]:
    """Retrieve precise system timezone, standard name, and UTC offset."""
    now_local = datetime.datetime.now()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if os.name != "nt":
        # Cross-platform fallback
        tz_name = time.tzname[0] if time.tzname else "UTC"
        raw_offset = now_local.astimezone().strftime("%z")
        formatted_offset = f"UTC{raw_offset[:3]}:{raw_offset[3:]}" if len(raw_offset) == 5 else "UTC+00:00"
        return {
            "status": "success",
            "timezone_name": tz_name,
            "standard_name": tz_name,
            "utc_offset": formatted_offset,
            "bias_minutes": 0,
            "daylight_disabled": True,
            "local_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        }

    try:
        tz = _DYNAMIC_TIME_ZONE_INFORMATION()
        res = ctypes.windll.kernel32.GetDynamicTimeZoneInformation(ctypes.byref(tz))
        # Bias = UTC - local time in minutes (e.g. UTC+5:45 has Bias = -345)
        offset_min = -int(tz.Bias)
        sign = "+" if offset_min >= 0 else "-"
        hours = abs(offset_min) // 60
        mins = abs(offset_min) % 60
        utc_offset = f"UTC{sign}{hours:02d}:{mins:02d}"

        zone_name = tz.TimeZoneKeyName or tz.StandardName or "Standard Time"
        standard_name = tz.StandardName or zone_name

        return {
            "status": "success",
            "timezone_name": zone_name,
            "standard_name": standard_name,
            "utc_offset": utc_offset,
            "bias_minutes": offset_min,
            "daylight_disabled": bool(tz.DynamicDaylightTimeDisabled),
            "local_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        raw_offset = now_local.astimezone().strftime("%z")
        formatted_offset = f"UTC{raw_offset[:3]}:{raw_offset[3:]}" if len(raw_offset) == 5 else "UTC"
        return {
            "status": "fallback",
            "timezone_name": "Local Timezone",
            "standard_name": "Standard Time",
            "utc_offset": formatted_offset,
            "bias_minutes": 0,
            "daylight_disabled": True,
            "local_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e),
        }


def get_ntp_server_config() -> Dict[str, Any]:
    """Inspect configured Windows Time service (W32Time) NTP servers in registry."""
    primary_server = "time.windows.com"
    sync_type = "NTP"
    known_servers: List[str] = []

    if os.name != "nt":
        return {
            "status": "unavailable",
            "primary_ntp_server": primary_server,
            "sync_type": sync_type,
            "configured_servers": ["pool.ntp.org"],
        }

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\W32Time\Parameters") as k:
            srv_raw, _ = winreg.QueryValueEx(k, "NtpServer")
            typ_raw, _ = winreg.QueryValueEx(k, "Type")
            if srv_raw:
                primary_server = srv_raw.split(",")[0].strip()
            if typ_raw:
                sync_type = str(typ_raw).strip()
    except Exception:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\DateTime\Servers") as k:
            n_vals = winreg.QueryInfoKey(k)[1]
            for i in range(n_vals):
                val_tuple = winreg.EnumValue(k, i)
                name, val = val_tuple[0], val_tuple[1]
                if name and val and str(val).strip() not in known_servers:
                    known_servers.append(str(val).strip())
    except Exception:
        pass

    if not known_servers:
        known_servers = [primary_server]

    return {
        "status": "success",
        "primary_ntp_server": primary_server,
        "sync_type": sync_type,
        "configured_servers": known_servers,
    }


def get_clock_summary() -> Dict[str, Any]:
    """Generate consolidated clock and timezone telemetry."""
    tz = get_system_timezone_info()
    ntp = get_ntp_server_config()

    return {
        "status": "success",
        "timezone": tz,
        "ntp": ntp,
    }


def clock_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting Windows clock, timezone, and NTP configuration."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "summary").lower().strip()

    if action in ("summary", "status", "clock"):
        summary_data = get_clock_summary()
        tz = summary_data["timezone"]
        ntp = summary_data["ntp"]
        summary = (
            f"Clock Telemetry: {tz['timezone_name']} ({tz['utc_offset']}). "
            f"Local: {tz['local_time']} | UTC: {tz['utc_time']}. "
            f"NTP Server: {ntp['primary_ntp_server']}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": summary_data,
        }, indent=2)

    if action in ("timezone", "tz"):
        tz = get_system_timezone_info()
        summary = f"System Timezone: {tz['timezone_name']} ({tz['utc_offset']}), Local time: {tz['local_time']}."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": tz,
        }, indent=2)

    if action in ("ntp", "servers", "sync"):
        ntp = get_ntp_server_config()
        summary = f"Primary NTP Server: {ntp['primary_ntp_server']} ({ntp['sync_type']}). Configured: {', '.join(ntp['configured_servers'])}."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": ntp,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, timezone, ntp.",
    }, indent=2)


TOOL = {
    "name": "clock_sentinel",
    "description": "Inspect Windows system timezone, standard name, UTC offset, local vs UTC timestamp, and configured NTP time synchronization servers.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "timezone", "ntp"],
                "description": "Clock or timezone operation to perform (default: 'summary').",
            },
        },
    },
    "handler": clock_sentinel,
}
