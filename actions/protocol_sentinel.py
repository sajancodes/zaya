"""Windows URI Protocol & Application Deep-Link Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects registered URL protocols and deep-link handlers across Windows Registry
(HKCU/HKLM Software\\Classes), validating executable associations and app integration.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import winreg

from core.execution_policy import require_owner


_POPULAR_APPS = (
    "discord", "spotify", "vscode", "telegram", "tg", "whatsapp",
    "slack", "zoommtg", "steam", "antigravity", "brave", "chrome",
    "edge", "mailto", "ms-settings", "obsidian", "notion"
)


def _extract_executable_path(command: str) -> Optional[str]:
    """Extract clean executable path from a shell open command string."""
    if not command:
        return None
    trimmed = command.strip()
    # Check for quoted executable path
    match_quoted = re.match(r'^"([^"]+\.exe)"', trimmed, re.IGNORECASE)
    if match_quoted:
        return match_quoted.group(1)

    # Check for unquoted executable ending with .exe (may contain spaces e.g. C:\Riot Games\...)
    match_unquoted = re.match(r'^([A-Za-z]:\\[^"/\n\r]+?\.exe)(?:\s+|$)', trimmed, re.IGNORECASE)
    if match_unquoted:
        return match_unquoted.group(1)

    return None


def get_registered_protocols(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan HKCU and HKLM classes for registered URL protocol handlers."""
    protocols_map: Dict[str, Dict[str, Any]] = {}
    search_term = search.lower().strip() if search else None

    # Scan HKCU first (user-specific overrides), then HKLM (system-wide)
    roots = [(winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")]

    for root_key, root_name in roots:
        try:
            with winreg.OpenKey(root_key, r"Software\Classes") as classes_key:
                subkeys_count = winreg.QueryInfoKey(classes_key)[0]
                for i in range(subkeys_count):
                    try:
                        subkey_name = winreg.EnumKey(classes_key, i)
                        if search_term and search_term not in subkey_name.lower():
                            continue

                        with winreg.OpenKey(classes_key, subkey_name) as sk:
                            try:
                                winreg.QueryValueEx(sk, "URL Protocol")
                            except FileNotFoundError:
                                continue

                            # Scheme has URL Protocol flag
                            scheme_lower = subkey_name.lower()
                            if scheme_lower in protocols_map:
                                continue

                            cmd = ""
                            try:
                                with winreg.OpenKey(sk, r"shell\open\command") as cmd_k:
                                    cmd = winreg.QueryValue(cmd_k, "")
                            except Exception:
                                pass

                            exe = _extract_executable_path(cmd)
                            exe_exists = bool(exe and Path(exe).is_file())

                            protocols_map[scheme_lower] = {
                                "scheme": subkey_name,
                                "source": root_name,
                                "command": cmd,
                                "executable": exe,
                                "executable_exists": exe_exists,
                            }
                    except Exception:
                        continue
        except Exception:
            continue

    return sorted(protocols_map.values(), key=lambda x: x["scheme"].lower())


def get_protocol_details(scheme: str) -> Dict[str, Any]:
    """Retrieve detailed registration and execution metadata for a specific URI scheme."""
    clean_scheme = scheme.lower().strip().rstrip(":")
    matches = get_registered_protocols(search=clean_scheme)
    exact = next((p for p in matches if p["scheme"].lower() == clean_scheme), None)

    if exact:
        return {
            "status": "registered",
            "scheme": exact["scheme"],
            "source": exact["source"],
            "command": exact["command"],
            "executable": exact["executable"],
            "executable_exists": exact["executable_exists"],
        }

    return {
        "status": "not_registered",
        "scheme": clean_scheme,
        "message": f"URI scheme '{clean_scheme}:' is not registered on this system.",
    }


def get_protocol_summary() -> Dict[str, Any]:
    """Generate high-level audit of registered protocols and popular applications."""
    all_protocols = get_registered_protocols()
    total_count = len(all_protocols)

    detected_popular = []
    for p in all_protocols:
        s_low = p["scheme"].lower()
        if any(app in s_low for app in _POPULAR_APPS):
            name = p["scheme"]
            if p.get("executable"):
                exe_name = Path(p["executable"]).name
                name = f"{p['scheme']} ({exe_name})"
            detected_popular.append(name)

    # Deduplicate while preserving order across base applications
    seen = set()
    unique_popular = []
    for item in detected_popular:
        base = re.split(r"[-_0-9]", item.split()[0].lower())[0]
        if base and base not in seen:
            seen.add(base)
            unique_popular.append(item)

    return {
        "status": "success",
        "total_protocols_registered": total_count,
        "popular_apps_detected_count": len(unique_popular),
        "popular_apps_sample": unique_popular[:12],
    }


def protocol_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Entry point for Windows protocol inspection and deep-link audits."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "summary").lower().strip()

    if action in ("summary", "status"):
        summary = get_protocol_summary()
        apps_str = ", ".join(summary["popular_apps_sample"]) if summary["popular_apps_sample"] else "None"
        summary_text = (
            f"Registered Protocols: {summary['total_protocols_registered']} total found. "
            f"Detected apps: {apps_str}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary_text,
            "data": summary,
        }, indent=2)

    if action in ("lookup", "check"):
        scheme = str(params.get("scheme") or "").strip()
        if not scheme:
            return json.dumps({"status": "error", "message": "Must provide 'scheme' to inspect (e.g. 'spotify', 'discord', 'vscode')."}, indent=2)
        details = get_protocol_details(scheme)
        is_reg = details["status"] == "registered"
        state_txt = f"registered -> {details.get('command', '')}" if is_reg else "NOT registered"
        summary_text = f"Protocol '{scheme}:' is {state_txt}."
        return json.dumps({
            "status": "success" if is_reg else "not_found",
            "summary": summary_text,
            "data": details,
        }, indent=2)

    if action in ("list", "all", "search"):
        query = params.get("query") or params.get("search")
        protocols = get_registered_protocols(search=str(query) if query else None)
        return json.dumps({
            "status": "success",
            "summary": f"Found {len(protocols)} registered protocol handler(s).",
            "data": {
                "count": len(protocols),
                "protocols": protocols[:100],  # bounded to avoid huge payload
            },
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, lookup, list.",
    }, indent=2)


TOOL = {
    "name": "protocol_sentinel",
    "description": "Inspect registered Windows URI protocols and application deep-link handlers (e.g. spotify:, discord:, vscode:, mailto:). Check executable associations and app readiness.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "lookup", "list"],
                "description": "Protocol inspection action (default: 'summary').",
            },
            "scheme": {
                "type": "STRING",
                "description": "Target URI scheme (e.g. 'discord', 'spotify', 'vscode') when action is 'lookup'.",
            },
            "query": {
                "type": "STRING",
                "description": "Search filter string when action is 'list'.",
            },
        },
    },
    "handler": protocol_sentinel,
}
