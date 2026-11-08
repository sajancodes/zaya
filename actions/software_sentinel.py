"""Installed Software & Application Package Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects, queries, and searches installed Windows applications across
64-bit and 32-bit machine registries and user uninstall registries.
Tracks application versions, publishers, install dates, and file locations.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

_REG_UNINSTALL_KEYS = [
    ("HKLM (64-bit)", 0, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM (32-bit)", 0, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU (User)", 1, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _audit_installed_software() -> List[Dict[str, Any]]:
    """Enumerate all installed software from Windows registry."""
    if os.name != "nt":
        return []

    import winreg
    apps: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for label, is_user, subpath in _REG_UNINSTALL_KEYS:
        hive = winreg.HKEY_CURRENT_USER if is_user else winreg.HKEY_LOCAL_MACHINE
        try:
            root_k = winreg.OpenKey(hive, subpath, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(root_k, i)
                    i += 1
                    try:
                        sk = winreg.OpenKey(root_k, sub_name, 0, winreg.KEY_READ)
                        try:
                            # Read display name
                            try:
                                name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                name = str(name).strip()
                            except OSError:
                                continue

                            if not name:
                                continue

                            # Skip Windows system components or updates without user value
                            try:
                                sys_comp, _ = winreg.QueryValueEx(sk, "SystemComponent")
                                if bool(sys_comp):
                                    continue
                            except OSError:
                                pass

                            norm_key = name.lower()
                            if norm_key in seen:
                                continue
                            seen.add(norm_key)

                            version = ""
                            try:
                                v_val, _ = winreg.QueryValueEx(sk, "DisplayVersion")
                                version = str(v_val).strip()
                            except OSError:
                                pass

                            publisher = ""
                            try:
                                p_val, _ = winreg.QueryValueEx(sk, "Publisher")
                                publisher = str(p_val).strip()
                            except OSError:
                                pass

                            install_date = ""
                            try:
                                d_val, _ = winreg.QueryValueEx(sk, "InstallDate")
                                install_date = str(d_val).strip()
                            except OSError:
                                pass

                            install_loc = ""
                            try:
                                l_val, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                install_loc = str(l_val).strip()
                            except OSError:
                                pass

                            apps.append({
                                "name": name,
                                "version": version or "Unknown",
                                "publisher": publisher or "Unknown",
                                "install_date": install_date or "Unknown",
                                "install_location": install_loc or "Unknown",
                                "registry_source": label,
                            })
                        finally:
                            winreg.CloseKey(sk)
                    except OSError:
                        pass
                except OSError:
                    break
            winreg.CloseKey(root_k)
        except Exception:
            continue

    return sorted(apps, key=lambda x: x["name"].lower())


def software_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Installed Software discovery and search actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    apps = _audit_installed_software()

    # 1. Overall Summary
    if action in ("summary", "status", "count"):
        sample_names = ", ".join(a["name"] for a in apps[:8])
        summary = (
            f"Software Sentinel: Discovered {len(apps)} installed application(s). "
            f"Key software: {sample_names}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "total_count": len(apps),
            "sample_applications": apps[:15],
        }, indent=2)

    # 2. Search Applications by Name / Publisher
    if action in ("search", "find", "query"):
        kw = str(parameters.get("keyword") or parameters.get("name") or "").lower().strip()
        if not kw:
            return json.dumps({"status": "error", "message": "Missing required parameter 'keyword'."}, indent=2)

        matches = [
            a for a in apps
            if kw in a["name"].lower() or kw in a["publisher"].lower()
        ]
        if matches:
            summary = f"Found {len(matches)} application(s) matching '{kw}': " + ", ".join(f"{m['name']} ({m['version']})" for m in matches[:10])
        else:
            summary = f"No installed application found matching '{kw}'."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "keyword": kw,
            "matches_count": len(matches),
            "matches": matches,
        }, indent=2)

    # 3. Check if specific application is installed
    if action in ("check", "is_installed"):
        name_query = str(parameters.get("name") or "").lower().strip()
        if not name_query:
            return json.dumps({"status": "error", "message": "Missing required parameter 'name'."}, indent=2)

        matched = next((a for a in apps if name_query in a["name"].lower()), None)
        if matched:
            summary = f"Yes, '{matched['name']}' is installed (version: {matched['version']}, publisher: {matched['publisher']})."
            return json.dumps({"status": "success", "installed": True, "summary": summary, "app": matched}, indent=2)
        else:
            summary = f"No installed application matching '{name_query}' was found."
            return json.dumps({"status": "success", "installed": False, "summary": summary}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, search, check."
    }, indent=2)


TOOL = {
    "name": "software_sentinel",
    "description": "Inspect and search all installed Windows software and desktop applications, query versions, publishers, install dates, and verify application presence.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "search", "check"],
                "description": "Software inspection action to execute (default: 'summary').",
            },
            "keyword": {
                "type": "STRING",
                "description": "Search keyword when action='search'.",
            },
            "name": {
                "type": "STRING",
                "description": "Application name to verify when action='check'.",
            },
        },
    },
    "handler": software_sentinel,
}
