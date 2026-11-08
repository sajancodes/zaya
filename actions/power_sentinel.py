"""Battery Health & Power Hardware Sentinel.
Created and developed by Sajan Rai for Zaya.

Performs deep battery health analysis via Windows powercfg XML telemetry and
psutil sensors: design capacity, full charge capacity, wear percentage,
hardware cycle count, battery chemistry, and power scheme management.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import psutil

from core.execution_policy import require_owner


def _get_live_battery_status() -> Dict[str, Any]:
    """Retrieve quick live battery sensor metrics via psutil."""
    sensor = psutil.sensors_battery()
    if sensor is None:
        return {
            "has_battery": False,
            "percent": 100,
            "power_plugged": True,
            "secs_left": None,
            "status_text": "AC Power (Desktop / No battery detected)",
        }

    secs = sensor.secsleft if sensor.secsleft != psutil.POWER_TIME_UNLIMITED else None
    if sensor.power_plugged:
        status_text = "Charging" if sensor.percent < 100 else "Fully Charged (AC Plugged)"
    else:
        status_text = "Discharging on Battery"

    return {
        "has_battery": True,
        "percent": int(sensor.percent),
        "power_plugged": bool(sensor.power_plugged),
        "secs_left": secs,
        "status_text": status_text,
    }


def _parse_battery_report_xml(xml_content: str) -> Dict[str, Any]:
    """Parse Windows powercfg XML battery report for deep health metrics."""
    result: Dict[str, Any] = {
        "has_battery": False,
        "manufacturer": "Unknown",
        "system_manufacturer": "Unknown",
        "chemistry": "Unknown",
        "design_capacity_mwh": 0,
        "full_charge_capacity_mwh": 0,
        "cycle_count": None,
        "health_percent": 100.0,
        "wear_percent": 0.0,
        "condition": "Unknown",
    }

    try:
        root = ET.fromstring(xml_content)
        # Namespace strip helper
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            text = (elem.text or "").strip()
            if not text:
                continue

            if tag == "SystemManufacturer" and result["system_manufacturer"] == "Unknown":
                result["system_manufacturer"] = text
            elif tag == "Manufacturer" and result["manufacturer"] == "Unknown":
                result["manufacturer"] = text
            elif tag == "Chemistry" and result["chemistry"] == "Unknown":
                result["chemistry"] = text
            elif tag == "DesignCapacity" and result["design_capacity_mwh"] == 0:
                try:
                    result["design_capacity_mwh"] = int(text)
                except ValueError:
                    pass
            elif tag == "FullChargeCapacity" and result["full_charge_capacity_mwh"] == 0:
                try:
                    result["full_charge_capacity_mwh"] = int(text)
                except ValueError:
                    pass
            elif tag == "CycleCount" and result["cycle_count"] is None:
                try:
                    result["cycle_count"] = int(text)
                except ValueError:
                    pass

        if result["design_capacity_mwh"] > 0 and result["full_charge_capacity_mwh"] > 0:
            result["has_battery"] = True
            des = result["design_capacity_mwh"]
            full = result["full_charge_capacity_mwh"]
            health = round((full / des) * 100.0, 1)
            wear = max(0.0, round(100.0 - health, 1))
            result["health_percent"] = min(100.0, health)
            result["wear_percent"] = wear

            if health >= 90.0:
                result["condition"] = "Excellent"
            elif health >= 80.0:
                result["condition"] = "Good"
            elif health >= 65.0:
                result["condition"] = "Moderate Wear"
            else:
                result["condition"] = "Degraded / High Wear"

    except Exception:
        pass

    return result


def _generate_battery_health_report() -> Dict[str, Any]:
    """Execute powercfg to produce temporary XML battery report and extract health."""
    live = _get_live_battery_status()
    if not live["has_battery"] and os.name != "nt":
        return {
            "has_battery": False,
            "live": live,
            "summary": "No battery hardware detected (Desktop or Non-Windows environment).",
        }

    if os.name != "nt":
        return {
            "has_battery": live["has_battery"],
            "live": live,
            "summary": f"Battery level: {live['percent']}%. Health report requires Windows powercfg.",
        }

    tmp_file = Path(tempfile.gettempdir()) / f"zaya_battery_{os.getpid()}_{int(time.time())}.xml"
    try:
        cmd = ["powercfg", "/batteryreport", "/xml", "/output", str(tmp_file)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8.0)
        if proc.returncode == 0 and tmp_file.exists():
            xml_text = tmp_file.read_text(encoding="utf-8", errors="replace")
            parsed = _parse_battery_report_xml(xml_text)
            parsed["live"] = live
            return parsed
    except Exception as e:
        return {
            "has_battery": live["has_battery"],
            "live": live,
            "error": str(e),
            "summary": f"Failed to generate battery report: {e}",
        }
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass

    return {
        "has_battery": live["has_battery"],
        "live": live,
        "summary": "Battery report could not be generated.",
    }


def _get_power_plans() -> List[Dict[str, Any]]:
    """List configured Windows power schemes via powercfg /list."""
    if os.name != "nt":
        return []

    plans = []
    try:
        proc = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, timeout=4.0)
        for line in proc.stdout.splitlines():
            line = line.strip()
            # Example: Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced) *
            match = re.search(r"Power Scheme GUID:\s+([0-9a-fA-F-]+)\s+\(([^)]+)\)(\s+\*)?", line)
            if match:
                guid, name, active = match.groups()
                plans.append({
                    "guid": guid,
                    "name": name,
                    "active": bool(active and "*" in active),
                })
    except Exception:
        pass
    return plans


def power_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Battery Health, Power Scheme, and Hardware Energy actions."""
    require_owner()
    action = str(parameters.get("action") or "health").lower().strip()

    # 1. Battery Health & Degradation Telemetry
    if action in ("health", "report", "summary"):
        report = _generate_battery_health_report()
        if not report.get("has_battery"):
            summary = "No battery detected (running on AC / Desktop workstation)."
            return json.dumps({"status": "success", "summary": summary, "data": report}, indent=2)

        des = report.get("design_capacity_mwh", 0)
        full = report.get("full_charge_capacity_mwh", 0)
        health = report.get("health_percent", 100.0)
        wear = report.get("wear_percent", 0.0)
        cycles = report.get("cycle_count", "N/A")
        condition = report.get("condition", "Good")
        live = report.get("live", {})
        percent = live.get("percent", 100)
        plugged_str = "AC Plugged" if live.get("power_plugged") else "Discharging"

        summary = (
            f"Battery Health: {condition} ({health}% of original design capacity). "
            f"Current Charge: {percent}% ({plugged_str}). "
            f"Full: {full:,} mWh / Design: {des:,} mWh. "
            f"Wear: {wear}%, Cycles: {cycles}."
        )
        return json.dumps({"status": "success", "summary": summary, "data": report}, indent=2)

    # 2. Live Battery Sensor Status
    if action in ("status", "live", "charge"):
        live = _get_live_battery_status()
        if not live["has_battery"]:
            summary = "System is running on direct AC power with no battery sensor."
        else:
            time_left = f", ~{round(live['secs_left']/60)} mins remaining" if live.get("secs_left") else ""
            summary = f"Battery: {live['percent']}% ({live['status_text']}{time_left})."
        return json.dumps({"status": "success", "summary": summary, "data": live}, indent=2)

    # 3. Power Plans / Schemes
    if action in ("plans", "schemes", "list_plans"):
        plans = _get_power_plans()
        active_plan = next((p["name"] for p in plans if p["active"]), "Unknown")
        summary = f"Active Windows power plan: '{active_plan}'. Total available plans: {len(plans)}."
        return json.dumps({"status": "success", "summary": summary, "plans": plans}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: health, status, plans."
    }, indent=2)


TOOL = {
    "name": "power_sentinel",
    "description": "Inspect deep battery health, full charge vs design capacity, degradation wear percentage, hardware cycle count, and active Windows power schemes.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["health", "status", "plans"],
                "description": "Power action to execute (default: 'health').",
            },
        },
    },
    "handler": power_sentinel,
}
