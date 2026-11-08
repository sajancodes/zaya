"""Windows Event Log & System Crash / BSOD Diagnostics Sentinel.
Created and developed by Sajan Rai for Zaya.

Queries and inspects Windows Event Logs for critical hardware errors, unexpected
system shutdowns (Kernel-Power Event 41 / 6008), and application crashes (Event 1000/1001)
using native wevtutil XML telemetry without third-party dependencies.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

_NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}


def _run_wevtutil_query(log_name: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Execute wevtutil with an XPath query and parse structured XML events."""
    cmd = [
        "wevtutil",
        "qe",
        log_name,
        f"/q:{query}",
        f"/c:{max(1, min(limit, 50))}",
        "/rd:true",
        "/f:xml",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        # wevtutil outputs multiple root <Event> siblings; wrap in a single parent container
        xml_data = f"<Events>{proc.stdout}</Events>"
        root = ET.fromstring(xml_data)

        parsed_events: List[Dict[str, Any]] = []
        for ev in root.findall("e:Event", _NS):
            sys_elem = ev.find("e:System", _NS)
            if sys_elem is None:
                continue

            event_id = sys_elem.findtext("e:EventID", default="0", namespaces=_NS)
            level_str = sys_elem.findtext("e:Level", default="0", namespaces=_NS)
            level_map = {"1": "Critical", "2": "Error", "3": "Warning", "4": "Information"}
            level = level_map.get(level_str, f"Level {level_str}")

            prov_elem = sys_elem.find("e:Provider", _NS)
            provider = prov_elem.attrib.get("Name", "Unknown") if prov_elem is not None else "Unknown"

            time_elem = sys_elem.find("e:TimeCreated", _NS)
            timestamp = time_elem.attrib.get("SystemTime", "Unknown") if time_elem is not None else "Unknown"

            record_id = sys_elem.findtext("e:EventRecordID", default="", namespaces=_NS)
            channel = sys_elem.findtext("e:Channel", default=log_name, namespaces=_NS)

            # Extract EventData key-value pairs
            data_dict: Dict[str, Any] = {}
            data_list: List[str] = []
            event_data = ev.find("e:EventData", _NS)
            if event_data is not None:
                for d in event_data.findall("e:Data", _NS):
                    key = d.attrib.get("Name")
                    val = (d.text or "").strip()
                    if key:
                        data_dict[key] = val
                    elif val:
                        data_list.append(val)

            parsed_events.append({
                "event_id": event_id,
                "level": level,
                "provider": provider,
                "timestamp": timestamp,
                "record_id": record_id,
                "channel": channel,
                "data": data_dict,
                "data_values": data_list,
            })

        return parsed_events

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ET.ParseError, Exception) as exc:
        logger.warning("wevtutil query failed on log %s: %s", log_name, exc)
        return []


def get_system_errors(limit: int = 10, channel: str = "System") -> List[Dict[str, Any]]:
    """Retrieve recent Critical (Level 1) and Error (Level 2) events from System or Application."""
    target_channel = "Application" if channel.lower() == "application" else "System"
    query = "*[System[(Level=1 or Level=2)]]"
    return _run_wevtutil_query(target_channel, query, limit=limit)


def get_application_crashes(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve recent Application Error (Event 1000) crashes."""
    query = "*[System[Provider[@Name='Application Error'] and (EventID=1000)]]"
    raw = _run_wevtutil_query("Application", query, limit=limit)
    crashes: List[Dict[str, Any]] = []
    for ev in raw:
        d = ev.get("data", {})
        crashes.append({
            "timestamp": ev.get("timestamp"),
            "event_id": ev.get("event_id"),
            "app_name": d.get("AppName") or "Unknown",
            "app_version": d.get("AppVersion") or "",
            "fault_module": d.get("ModuleName") or "Unknown",
            "exception_code": d.get("ExceptionCode") or "Unknown",
            "fault_offset": d.get("FaultingOffset") or "",
            "app_path": d.get("AppPath") or "",
        })
    return crashes


def get_unexpected_shutdowns(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve Kernel-Power Event 41 (sudden reboot / BSOD) and Event 6008 events."""
    query = "*[System[(EventID=41 or EventID=6008)]]"
    raw = _run_wevtutil_query("System", query, limit=limit)
    shutdowns: List[Dict[str, Any]] = []
    for ev in raw:
        d = ev.get("data", {})
        shutdowns.append({
            "timestamp": ev.get("timestamp"),
            "event_id": ev.get("event_id"),
            "provider": ev.get("provider"),
            "bugcheck_code": d.get("BugcheckCode") or "0",
            "power_button_timestamp": d.get("PowerButtonTimestamp") or "0",
            "sleep_in_progress": d.get("SleepInProgress") or "0",
        })
    return shutdowns


def get_event_log_summary() -> Dict[str, Any]:
    """Compile a top-level health summary of system errors, crashes, and unexpected shutdowns."""
    sys_errors = get_system_errors(limit=5, channel="System")
    app_crashes = get_application_crashes(limit=3)
    shutdowns = get_unexpected_shutdowns(limit=3)

    if shutdowns:
        health_status = "Attention Required (Unexpected shutdown or reboot detected)"
    elif app_crashes:
        health_status = "Degraded (Application crashes detected)"
    elif sys_errors:
        health_status = "Warning (System errors reported in event log)"
    else:
        health_status = "Healthy (Zero critical errors or crashes logged)"

    return {
        "status": "success",
        "health_status": health_status,
        "recent_system_errors_count": len(sys_errors),
        "recent_app_crashes_count": len(app_crashes),
        "recent_unexpected_shutdowns_count": len(shutdowns),
        "latest_system_error": sys_errors[0] if sys_errors else None,
        "latest_app_crash": app_crashes[0] if app_crashes else None,
        "latest_unexpected_shutdown": shutdowns[0] if shutdowns else None,
    }


def event_log_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Windows Event Log diagnostics and crash investigation actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    limit = int(parameters.get("limit") or 10)
    channel = str(parameters.get("channel") or "System").strip()

    if action in ("summary", "health", "report"):
        summary_data = get_event_log_summary()
        latest_crash = summary_data.get("latest_app_crash")
        crash_desc = f" Latest crash: {latest_crash['app_name']} ({latest_crash['fault_module']})." if latest_crash else ""
        summary_text = (
            f"Event Log Diagnostics: {summary_data['health_status']}. "
            f"Logged: {summary_data['recent_system_errors_count']} system errors, "
            f"{summary_data['recent_app_crashes_count']} app crashes, "
            f"{summary_data['recent_unexpected_shutdowns_count']} unexpected shutdowns.{crash_desc}"
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": summary_data}, indent=2)

    if action in ("system_errors", "errors", "system"):
        errors = get_system_errors(limit=limit, channel=channel)
        summary_text = f"Retrieved {len(errors)} critical/error events from Windows {channel} log."
        return json.dumps({"status": "success", "summary": summary_text, "channel": channel, "events": errors}, indent=2)

    if action in ("crashes", "app_crashes", "crash"):
        crashes = get_application_crashes(limit=limit)
        summary_text = f"Retrieved {len(crashes)} recent application crashes."
        return json.dumps({"status": "success", "summary": summary_text, "crashes": crashes}, indent=2)

    if action in ("shutdowns", "reboots", "bsod"):
        shutdowns = get_unexpected_shutdowns(limit=limit)
        summary_text = f"Retrieved {len(shutdowns)} unexpected shutdown / Kernel-Power events."
        return json.dumps({"status": "success", "summary": summary_text, "shutdowns": shutdowns}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, system_errors, crashes, shutdowns."
    }, indent=2)


TOOL = {
    "name": "event_log_sentinel",
    "description": "Inspect Windows Event Logs for critical system errors, application crashes (Event 1000), and unexpected shutdowns / BSOD bugchecks (Kernel-Power 41).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "system_errors", "crashes", "shutdowns"],
                "description": "Diagnostics action to execute (default: 'summary').",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of event entries to retrieve (default: 10).",
            },
            "channel": {
                "type": "STRING",
                "enum": ["System", "Application"],
                "description": "Windows Event Log channel to query (default: 'System').",
            },
        },
    },
    "handler": event_log_sentinel,
}
