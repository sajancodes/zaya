"""Windows Power Schemes & Performance Mode Sentinel.
Created and developed by Sajan Rai for Zaya.

Audits installed Windows power schemes (Balanced, Ultimate, High Performance, Power Saver)
and dynamically switches active power profiles via powercfg.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


# Well-known Windows Power Scheme GUIDs
GUID_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
GUID_HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_POWER_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
GUID_ULTIMATE_PERFORMANCE = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def list_power_schemes() -> List[Dict[str, Any]]:
    """List all registered Windows power schemes and indicate the active profile."""
    if os.name != "nt":
        return [{"guid": GUID_BALANCED, "name": "Balanced", "active": True}]

    schemes: List[Dict[str, Any]] = []
    try:
        out = subprocess.check_output(["powercfg", "/list"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r"Power Scheme GUID:\s+([a-f0-9-]+)\s+\(([^)]+)\)(\s+\*)?", line, re.IGNORECASE)
            if m:
                schemes.append({
                    "guid": m.group(1).lower(),
                    "name": m.group(2).strip(),
                    "active": bool(m.group(3)),
                })
    except Exception:
        pass
    return schemes


def get_active_power_scheme() -> Dict[str, Any]:
    """Retrieve the currently active power scheme."""
    schemes = list_power_schemes()
    for s in schemes:
        if s.get("active"):
            return {
                "status": "success",
                "name": s["name"],
                "guid": s["guid"],
                "all_schemes": schemes,
            }

    if schemes:
        return {
            "status": "success",
            "name": schemes[0]["name"],
            "guid": schemes[0]["guid"],
            "all_schemes": schemes,
        }

    return {
        "status": "unknown",
        "name": "Balanced",
        "guid": GUID_BALANCED,
        "all_schemes": [],
    }


def switch_power_scheme(target: str) -> Dict[str, Any]:
    """Switch active Windows power scheme by name (e.g. 'performance', 'balanced') or GUID."""
    if os.name != "nt":
        return {"status": "unavailable", "message": "Power scheme switching requires Windows."}

    clean_target = target.strip().lower()
    schemes = list_power_schemes()
    matched_scheme = None

    # 1. Exact GUID match
    for s in schemes:
        if s["guid"] == clean_target:
            matched_scheme = s
            break

    # 2. Performance alias matching
    if not matched_scheme and any(kw in clean_target for kw in ("perf", "ultimate", "high", "gaming", "max")):
        for s in schemes:
            low_name = s["name"].lower()
            if any(kw in low_name for kw in ("ultimate", "high performance", "performance", "turbo")):
                matched_scheme = s
                break

    # 3. Balanced alias matching
    if not matched_scheme and any(kw in clean_target for kw in ("balance", "normal", "default")):
        for s in schemes:
            if "balance" in s["name"].lower():
                matched_scheme = s
                break

    # 4. Power saver alias matching
    if not matched_scheme and any(kw in clean_target for kw in ("save", "saver", "eco", "low", "battery")):
        for s in schemes:
            if any(kw in s["name"].lower() for kw in ("save", "eco", "quiet")):
                matched_scheme = s
                break

    # 5. Generic substring match
    if not matched_scheme:
        for s in schemes:
            if clean_target in s["name"].lower():
                matched_scheme = s
                break

    # If performance requested but no high perf scheme installed, duplicate Ultimate Performance
    if not matched_scheme and any(kw in clean_target for kw in ("perf", "ultimate", "high")):
        try:
            # Try duplicate Ultimate Performance scheme
            dup_out = subprocess.check_output(
                ["powercfg", "-duplicatescheme", GUID_ULTIMATE_PERFORMANCE],
                text=True, stderr=subprocess.DEVNULL
            )
            m_dup = re.search(r"([a-f0-9-]{36})", dup_out)
            if m_dup:
                matched_scheme = {"guid": m_dup.group(1).lower(), "name": "Ultimate Performance"}
        except Exception:
            pass

    if not matched_scheme:
        available = [s["name"] for s in schemes]
        return {
            "status": "error",
            "message": f"Could not find power scheme matching '{target}'. Available plans: {', '.join(available)}.",
        }

    try:
        subprocess.check_call(
            ["powercfg", "/setactive", matched_scheme["guid"]],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return {
            "status": "success",
            "name": matched_scheme["name"],
            "guid": matched_scheme["guid"],
            "message": f"Switched power scheme to '{matched_scheme['name']}'.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to switch power scheme: {e}"}


def power_plan_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and switching Windows power schemes."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()

    if action in ("status", "summary", "current"):
        active = get_active_power_scheme()
        available_names = [s["name"] for s in active.get("all_schemes", [])]
        summary = (
            f"Active Power Scheme: '{active['name']}' (*). "
            f"Available schemes: {', '.join(available_names)}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": active,
        }, indent=2)

    if action in ("switch", "set", "change"):
        plan = params.get("plan") or params.get("mode") or params.get("scheme")
        if not plan:
            return json.dumps({
                "status": "error",
                "message": "Must provide 'plan' or 'mode' (e.g. 'performance', 'balanced', 'power saver')."
            }, indent=2)

        res = switch_power_scheme(str(plan))
        return json.dumps(res, indent=2)

    if action in ("list", "plans", "schemes"):
        schemes = list_power_schemes()
        return json.dumps({
            "status": "success",
            "summary": f"Detected {len(schemes)} power scheme(s).",
            "data": {"schemes": schemes},
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, switch, list.",
    }, indent=2)


TOOL = {
    "name": "power_plan_sentinel",
    "description": "Inspect and switch Windows power schemes (Balanced, Ultimate Performance, High Performance, Power Saver). Fulfills owner power mode switching requests directly.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "switch", "list"],
                "description": "Power plan action to perform (default: 'status').",
            },
            "plan": {
                "type": "STRING",
                "description": "Target power scheme or mode (e.g. 'performance', 'balanced', 'power saver', 'ultimate') when action is 'switch'.",
            },
        },
    },
    "handler": power_plan_sentinel,
}
