"""Windows Background Service Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects, queries, and audits Windows Services (daemons, databases, background tasks,
WSL, Docker, audio subsystem, network daemons) using psutil native win_service APIs.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import psutil

from core.execution_policy import require_owner

_KEY_DEV_SERVICES = (
    ("Audiosrv", "Windows Audio"),
    ("AudioEndpointBuilder", "Windows Audio Endpoint Builder"),
    ("wuauserv", "Windows Update"),
    ("LanmanWorkstation", "Workstation Network"),
    ("Spooler", "Print Spooler"),
    ("wslservice", "Windows Subsystem for Linux"),
    ("com.docker.service", "Docker Desktop Service"),
    ("sshd", "OpenSSH SSH Server"),
    ("postgresql-x64", "PostgreSQL Database Server"),
    ("MySQL", "MySQL Database Server"),
    ("MongoDB", "MongoDB Database Server"),
    ("Redis", "Redis Server"),
)


def _get_services_summary() -> Dict[str, Any]:
    """Inspect all registered Windows services and key system subsystems."""
    if os.name != "nt" or not hasattr(psutil, "win_service_iter"):
        return {
            "total": 0,
            "running_count": 0,
            "stopped_count": 0,
            "key_subsystems": [],
            "message": "Windows Service management is only available on Windows OS.",
        }

    total = 0
    running_count = 0
    stopped_count = 0
    service_dict: Dict[str, Any] = {}

    for s in psutil.win_service_iter():
        total += 1
        try:
            st = s.status()
            if st == "running":
                running_count += 1
            else:
                stopped_count += 1
            service_dict[s.name().lower()] = s
        except Exception:
            pass

    key_subsystems: List[Dict[str, Any]] = []
    for s_name, label in _KEY_DEV_SERVICES:
        matched = None
        for k, v in service_dict.items():
            if k == s_name.lower() or s_name.lower() in k:
                matched = v
                break

        if matched:
            try:
                info = matched.as_dict()
                key_subsystems.append({
                    "name": info.get("name"),
                    "label": label,
                    "status": info.get("status"),
                    "start_type": info.get("start_type"),
                    "pid": info.get("pid"),
                })
            except Exception:
                pass

    return {
        "total": total,
        "running_count": running_count,
        "stopped_count": stopped_count,
        "key_subsystems": key_subsystems,
    }


def _search_services(keyword: str) -> List[Dict[str, Any]]:
    """Search registered services by name or description."""
    if os.name != "nt" or not hasattr(psutil, "win_service_iter"):
        return []

    low_kw = keyword.lower().strip()
    results: List[Dict[str, Any]] = []

    for s in psutil.win_service_iter():
        try:
            n = s.name().lower()
            dn = s.display_name().lower()
            desc = (s.description() or "").lower()
            if low_kw in n or low_kw in dn or low_kw in desc:
                results.append({
                    "name": s.name(),
                    "display_name": s.display_name(),
                    "status": s.status(),
                    "start_type": s.start_type(),
                    "pid": s.pid(),
                })
        except Exception:
            continue

    return results


def _get_service_detail(name: str) -> Optional[Dict[str, Any]]:
    """Get full properties for a specific named Windows service."""
    if os.name != "nt" or not hasattr(psutil, "win_service_get"):
        return None

    try:
        s = psutil.win_service_get(name)
        return s.as_dict()
    except Exception:
        # Try case-insensitive search
        low = name.lower().strip()
        for s in psutil.win_service_iter():
            try:
                if s.name().lower() == low or s.display_name().lower() == low:
                    return s.as_dict()
            except Exception:
                continue
    return None


def service_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Windows Service discovery and inspection actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()

    # 1. Overall Services Summary
    if action in ("summary", "status", "overview"):
        data = _get_services_summary()
        active_subsystems = [s["label"] for s in data.get("key_subsystems", []) if s.get("status") == "running"]
        active_str = ", ".join(active_subsystems[:4]) if active_subsystems else "Standard Windows Subsystems"
        summary = (
            f"Windows Services: {data['running_count']} running out of {data['total']} registered. "
            f"Active subsystems include: {active_str}."
        )
        return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

    # 2. Search Services
    if action in ("search", "find", "query"):
        kw = str(parameters.get("keyword") or parameters.get("name") or "").strip()
        if not kw:
            return json.dumps({"status": "error", "message": "Missing required parameter 'keyword'."}, indent=2)

        matches = _search_services(kw)
        if matches:
            summary = f"Found {len(matches)} service(s) matching '{kw}': " + ", ".join(f"{s['name']} ({s['status']})" for s in matches[:8])
        else:
            summary = f"No services found matching '{kw}'."
        return json.dumps({"status": "success", "summary": summary, "keyword": kw, "matches": matches}, indent=2)

    # 3. Get / Inspect Specific Service
    if action in ("get", "inspect", "detail"):
        name = str(parameters.get("name") or parameters.get("service") or "").strip()
        if not name:
            return json.dumps({"status": "error", "message": "Missing required parameter 'name'."}, indent=2)

        detail = _get_service_detail(name)
        if not detail:
            return json.dumps({"status": "error", "message": f"Service '{name}' was not found on this system."}, indent=2)

        summary = (
            f"Service '{detail.get('display_name')}' ({detail.get('name')}): Status: {detail.get('status')} "
            f"[PID: {detail.get('pid') or 'N/A'}, Startup: {detail.get('start_type')}]. User: {detail.get('username')}."
        )
        return json.dumps({"status": "success", "summary": summary, "service": detail}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, search, get."
    }, indent=2)


TOOL = {
    "name": "service_sentinel",
    "description": "Inspect, query, and search Windows background services (daemons, audio, database servers, WSL, Docker, Windows Update) and monitor their real-time execution states.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "search", "get"],
                "description": "Service operation to execute (default: 'summary').",
            },
            "keyword": {
                "type": "STRING",
                "description": "Keyword to search services by name or description.",
            },
            "name": {
                "type": "STRING",
                "description": "Exact service name or display name to inspect in detail.",
            },
        },
    },
    "handler": service_sentinel,
}
