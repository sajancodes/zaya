"""Environment Variable & System PATH Sentinel.
Created and developed by Sajan Rai for Zaya.

Audits system and user PATH variables for orphaned directories, duplicates,
and security issues. Inspects developer tool toolchains (Git, Node, Python,
Rust, Go, Flutter, Android SDK) and verifies toolchain resolutions safely.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set

from core.execution_policy import require_owner

_REDACTED_PATTERNS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "AUTH", "PASS")

_COMMON_DEV_TOOLS = (
    "git",
    "python",
    "node",
    "npm",
    "pnpm",
    "yarn",
    "bun",
    "deno",
    "rustc",
    "cargo",
    "go",
    "flutter",
    "dart",
    "java",
    "docker",
    "kubectl",
    "adb",
    "code",
    "pwsh",
)


def _audit_path() -> Dict[str, Any]:
    """Examine system PATH entries for missing directories and duplicates."""
    raw_path = os.environ.get("PATH", "")
    entries = [e.strip() for e in raw_path.split(os.pathsep) if e.strip()]

    valid_entries: List[str] = []
    missing_entries: List[str] = []
    duplicates: List[str] = []
    seen: Set[str] = set()

    for entry in entries:
        norm = os.path.normpath(entry).lower()
        if norm in seen:
            duplicates.append(entry)
        else:
            seen.add(norm)

        if os.path.exists(entry):
            valid_entries.append(entry)
        else:
            missing_entries.append(entry)

    health = "Clean"
    if missing_entries and duplicates:
        health = "Requires Attention (Missing directories & duplicates)"
    elif missing_entries:
        health = f"Degraded ({len(missing_entries)} dead path(s))"
    elif duplicates:
        health = f"Minor ({len(duplicates)} duplicate(s))"

    return {
        "total_entries": len(entries),
        "valid_count": len(valid_entries),
        "missing_count": len(missing_entries),
        "duplicate_count": len(duplicates),
        "health": health,
        "missing_samples": missing_entries[:10],
        "duplicate_samples": duplicates[:10],
    }


def _get_tool_version(binary_path: str, tool_name: str) -> Optional[str]:
    """Attempt a fast version query for a discovered developer tool."""
    flag = "--version"
    if tool_name in ("go",):
        flag = "version"
    try:
        proc = subprocess.run(
            [binary_path, flag],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0].strip() if proc.stdout else ""
            if not first_line and proc.stderr:
                first_line = proc.stderr.splitlines()[0].strip()
            return first_line[:80]
    except Exception:
        pass
    return None


def _audit_developer_tools() -> Dict[str, Any]:
    """Scan PATH for standard developer compilers, runtimes, and CLIs."""
    installed: List[Dict[str, Any]] = []
    missing: List[str] = []

    discovered = []
    for tool in _COMMON_DEV_TOOLS:
        loc = shutil.which(tool)
        if loc:
            discovered.append((tool, loc))
        else:
            missing.append(tool)

    def _probe(item: tuple[str, str]) -> Dict[str, Any]:
        t_name, t_loc = item
        ver = _get_tool_version(t_loc, t_name)
        return {"name": t_name, "path": t_loc, "version": ver or "Discovered"}

    if discovered:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(discovered), 8)) as executor:
            installed = list(executor.map(_probe, discovered))

    return {
        "installed_count": len(installed),
        "missing_count": len(missing),
        "installed": installed,
        "missing": missing,
    }


def _inspect_variable(var_name: str) -> Dict[str, Any]:
    """Inspect a specific environment variable with redaction safety."""
    upper = var_name.upper()
    if any(pat in upper for pat in _REDACTED_PATTERNS):
        return {
            "name": var_name,
            "status": "redacted",
            "message": "Sensitive credential variable is redacted for safety.",
        }

    val = os.environ.get(var_name)
    if val is None:
        return {"name": var_name, "exists": False}

    is_path = os.path.sep in val or "/" in val
    exists_on_disk = os.path.exists(val) if is_path else None

    return {
        "name": var_name,
        "exists": True,
        "value": val,
        "is_path": is_path,
        "exists_on_disk": exists_on_disk,
    }


def env_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Environment Variable and PATH Sentinel actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()

    # 1. PATH Audit
    if action in ("path", "audit", "path_audit"):
        res = _audit_path()
        summary = (
            f"PATH Audit: {res['total_entries']} total entries ({res['valid_count']} valid, "
            f"{res['missing_count']} missing/dead, {res['duplicate_count']} duplicates). Status: {res['health']}."
        )
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 2. Developer Toolchain Audit
    if action in ("tools", "dev_tools", "toolchain"):
        res = _audit_developer_tools()
        tools_list = ", ".join(t["name"] for t in res["installed"])
        summary = f"Developer Toolchain: Found {res['installed_count']} active tool(s): {tools_list}."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 3. Specific Variable Query
    if action in ("get", "var", "variable"):
        var_name = str(parameters.get("name") or "").strip()
        if not var_name:
            return json.dumps({"status": "error", "message": "Missing required parameter 'name'."}, indent=2)
        res = _inspect_variable(var_name)
        if not res.get("exists", False) and res.get("status") != "redacted":
            summary = f"Environment variable '{var_name}' is not set."
        elif res.get("status") == "redacted":
            summary = f"Environment variable '{var_name}' is confidential (redacted)."
        else:
            disk_info = ""
            if res.get("exists_on_disk") is True:
                disk_info = " [valid path]"
            elif res.get("exists_on_disk") is False:
                disk_info = " [MISSING on disk]"
            summary = f"{var_name} = '{res['value']}'{disk_info}."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 4. Overall Environment Summary
    if action == "summary":
        path_res = _audit_path()
        tools_res = _audit_developer_tools()
        summary = (
            f"Environment Sentinel: PATH has {path_res['total_entries']} entries ({path_res['missing_count']} dead). "
            f"{tools_res['installed_count']} developer CLIs available ({', '.join(t['name'] for t in tools_res['installed'][:5])})."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "path": path_res,
            "developer_tools": tools_res,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, path, tools, get."
    }, indent=2)


TOOL = {
    "name": "env_sentinel",
    "description": "Audit system and user PATH directories, detect broken paths and duplicates, inspect developer CLI toolchains (Git, Node, Python, ADB), and inspect environment variables safely.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "path", "tools", "get"],
                "description": "Environment action to execute (default: 'summary').",
            },
            "name": {
                "type": "STRING",
                "description": "Variable name to inspect when action='get' (e.g. 'JAVA_HOME').",
            },
        },
    },
    "handler": env_sentinel,
}
