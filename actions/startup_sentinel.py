"""Windows Startup Programs & Auto-Run Sentinel.
Created and developed by Sajan Rai for Zaya.

Audits Windows startup programs across HKCU/HKLM Run registry keys and
User/Common Start Menu Startup directories. Identifies command paths,
detects orphaned / ghost startup entries, and verifies target binaries.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

_REG_LOCATIONS = [
    ("HKCU\\Run", r"Software\Microsoft\Windows\CurrentVersion\Run", True),
    ("HKLM\\Run", r"Software\Microsoft\Windows\CurrentVersion\Run", False),
]


def _extract_target_path(cmd_str: str) -> Optional[str]:
    """Extract primary executable path from a shell command string."""
    if not cmd_str:
        return None

    cmd = os.path.expandvars(cmd_str.strip())
    # Handle quoted path: e.g. "C:\Path\to\exe.exe" --arg
    if cmd.startswith('"'):
        end_q = cmd.find('"', 1)
        if end_q != -1:
            return cmd[1:end_q]

    # Handle unquoted: split by first space or take whole if exists
    parts = cmd.split()
    if parts:
        cand = parts[0]
        if os.path.exists(cand):
            return cand
        # Sometimes paths have spaces without quotes; check if full or partial exists
        for i in range(len(parts), 0, -1):
            joined = " ".join(parts[:i])
            if os.path.exists(joined):
                return joined
        return parts[0]

    return cmd


def _audit_registry_startup() -> List[Dict[str, Any]]:
    """Query HKCU and HKLM Run keys."""
    if os.name != "nt":
        return []

    import winreg
    results: List[Dict[str, Any]] = []

    for label, subkey, is_user in _REG_LOCATIONS:
        hive = winreg.HKEY_CURRENT_USER if is_user else winreg.HKEY_LOCAL_MACHINE
        try:
            k = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                    i += 1
                    val_str = str(val).strip()
                    target = _extract_target_path(val_str)
                    if target:
                        if os.path.isabs(target):
                            exists = os.path.exists(target)
                        else:
                            which_path = shutil.which(target)
                            exists = bool(which_path and os.path.exists(which_path))
                    else:
                        exists = None

                    results.append({
                        "name": name,
                        "command": val_str,
                        "target_path": target,
                        "exists_on_disk": exists,
                        "source": label,
                    })
                except OSError:
                    break
            winreg.CloseKey(k)
        except Exception:
            continue

    return results


def _audit_folder_startup() -> List[Dict[str, Any]]:
    """Query user and all-users Start Menu Startup directories."""
    results: List[Dict[str, Any]] = []

    appdata = os.environ.get("APPDATA", "")
    progdata = os.environ.get("PROGRAMDATA", "")

    folders = [
        ("User Startup Folder", os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")),
        ("Common Startup Folder", os.path.join(progdata, r"Microsoft\Windows\Start Menu\Programs\Startup")),
    ]

    for label, f_path in folders:
        if not f_path or not os.path.exists(f_path):
            continue

        try:
            for item in os.listdir(f_path):
                if item.lower() in ("desktop.ini", "thumbs.db"):
                    continue
                full_item = os.path.join(f_path, item)
                results.append({
                    "name": item,
                    "command": full_item,
                    "target_path": full_item,
                    "exists_on_disk": True,
                    "source": label,
                })
        except Exception:
            continue

    return results


def _get_all_startup_entries() -> Dict[str, Any]:
    """Aggregate startup entries and detect dead / ghost entries."""
    reg_entries = _audit_registry_startup()
    folder_entries = _audit_folder_startup()
    all_entries = reg_entries + folder_entries

    dead_entries = [e for e in all_entries if e.get("exists_on_disk") is False]

    return {
        "total_count": len(all_entries),
        "valid_count": len(all_entries) - len(dead_entries),
        "dead_count": len(dead_entries),
        "entries": all_entries,
        "dead_entries": dead_entries,
    }


def startup_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Startup Programs and Auto-Run Sentinel actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    data = _get_all_startup_entries()

    # 1. Summary / All Entries
    if action in ("summary", "status", "list", "all"):
        dead_str = f" ({data['dead_count']} orphaned/dead targets detected)" if data["dead_count"] > 0 else " (all targets valid)"
        sample_names = ", ".join(e["name"] for e in data["entries"][:6])
        summary = (
            f"Startup Sentinel: Found {data['total_count']} auto-run entries{dead_str}. "
            f"Active entries: {sample_names}."
        )
        return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

    # 2. Dead / Orphaned Ghost Entries Only
    if action in ("dead", "ghost", "orphaned"):
        dead = data["dead_entries"]
        if dead:
            summary = f"Detected {len(dead)} orphaned startup entry(s): " + ", ".join(f"{e['name']} [{e['source']}]" for e in dead)
        else:
            summary = "No dead or orphaned startup entries detected. All startup programs exist on disk."
        return json.dumps({"status": "success", "summary": summary, "dead_count": len(dead), "entries": dead}, indent=2)

    # 3. Search Entries
    if action in ("search", "find"):
        kw = str(parameters.get("keyword") or "").lower().strip()
        if not kw:
            return json.dumps({"status": "error", "message": "Missing required parameter 'keyword'."}, indent=2)

        matches = [
            e for e in data["entries"]
            if kw in e["name"].lower() or kw in e.get("command", "").lower()
        ]
        if matches:
            summary = f"Found {len(matches)} startup entry(s) matching '{kw}': " + ", ".join(e["name"] for e in matches)
        else:
            summary = f"No startup entries found matching '{kw}'."
        return json.dumps({"status": "success", "summary": summary, "keyword": kw, "matches": matches}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, dead, search."
    }, indent=2)


TOOL = {
    "name": "startup_sentinel",
    "description": "Inspect Windows startup and auto-run programs across HKCU/HKLM Run registry keys and Start Menu Startup directories, detecting orphaned ghost entries.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "dead", "search"],
                "description": "Startup audit action to execute (default: 'summary').",
            },
            "keyword": {
                "type": "STRING",
                "description": "Keyword to filter startup entries when action='search'.",
            },
        },
    },
    "handler": startup_sentinel,
}
