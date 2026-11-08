"""Windows Firewall & Network Security Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects Windows Defender Firewall active profile states (Domain, Private, Public),
audits default inbound/outbound packet filtering policies, and inspects firewall rules via netsh.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)


def _parse_netsh_key_values(raw_text: str) -> List[Dict[str, str]]:
    """Parse colon-delimited blocks from netsh advfirewall output."""
    items: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    for line in raw_text.splitlines():
        line_str = line.strip()
        if not line_str or line_str == "Ok." or line_str.startswith("---"):
            continue

        if line_str.endswith("Profile Settings:"):
            if current:
                items.append(current)
            prof_name = line_str.split()[0].strip()
            current = {"profile": prof_name}
            continue

        if line_str.startswith("Rule Name:"):
            if current:
                items.append(current)
            rule_name = line_str.partition(":")[2].strip()
            current = {"rule_name": rule_name}
            continue

        if ":" in line_str:
            key, sep, val = line_str.partition(":")
            clean_key = key.strip().lower().replace(" ", "_")
            current[clean_key] = val.strip()
        else:
            parts = re.split(r"\s{2,}", line_str, maxsplit=1)
            if len(parts) == 2:
                clean_key = parts[0].strip().lower().replace(" ", "_")
                current[clean_key] = parts[1].strip()

    if current:
        items.append(current)

    return items


def get_firewall_profiles() -> Dict[str, Dict[str, Any]]:
    """Query state and policies of all Windows Firewall profiles (Domain, Private, Public)."""
    cmd = ["netsh", "advfirewall", "show", "allprofiles"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {}

        blocks = _parse_netsh_key_values(proc.stdout)
        profiles: Dict[str, Dict[str, Any]] = {}

        for b in blocks:
            prof = b.get("profile")
            if not prof:
                continue

            state = b.get("state", "UNKNOWN").upper()
            policy = b.get("firewall_policy", "")
            inbound = "Block" if "blockinbound" in policy.lower() else "Allow"
            outbound = "Allow" if "allowoutbound" in policy.lower() else "Block"

            profiles[prof] = {
                "state": state,
                "is_active": state == "ON",
                "policy": policy,
                "inbound_default": inbound,
                "outbound_default": outbound,
                "logging_dropped": b.get("logdroppedconnections", "Disable"),
            }

        return profiles

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("netsh allprofiles query failed: %s", exc)
        return {}


def get_firewall_rule(rule_name: str) -> List[Dict[str, Any]]:
    """Retrieve detailed settings for a specific named firewall rule."""
    cmd = ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name.strip()}"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip() or "No rules match" in proc.stdout:
            return []

        return _parse_netsh_key_values(proc.stdout)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("netsh rule query failed for %s: %s", rule_name, exc)
        return []


def search_firewall_rules(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search inbound firewall rules matching keyword or port."""
    cmd = ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        all_rules = _parse_netsh_key_values(proc.stdout)
        q = query.lower().strip()
        matches: List[Dict[str, Any]] = []

        for r in all_rules:
            name = r.get("rule_name", "").lower()
            port = r.get("localport", "").lower()
            group = r.get("grouping", "").lower()

            if q in name or q in port or q in group:
                matches.append(r)
                if len(matches) >= limit:
                    break

        return matches

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("netsh search rules failed: %s", exc)
        return []


def get_firewall_summary() -> Dict[str, Any]:
    """Compile comprehensive Windows Firewall security posture."""
    profiles = get_firewall_profiles()

    disabled_profiles = [p for p, data in profiles.items() if not data.get("is_active")]
    all_secure = len(disabled_profiles) == 0 and len(profiles) > 0

    status_str = (
        "Secure (Firewall active on Domain, Private, and Public profiles)"
        if all_secure
        else f"Warning (Firewall disabled on: {', '.join(disabled_profiles)})"
    )

    return {
        "status": "success",
        "security_posture": status_str,
        "all_profiles_enabled": all_secure,
        "disabled_profiles": disabled_profiles,
        "profiles": profiles,
    }


def firewall_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Windows Firewall inspection and security audits."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    rule_name = str(parameters.get("rule_name") or parameters.get("name") or "").strip()
    query = str(parameters.get("query") or "").strip()
    limit = int(parameters.get("limit") or 10)

    if action in ("summary", "status", "health"):
        summary = get_firewall_summary()
        summary_text = f"Windows Firewall: {summary['security_posture']}."
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("profiles", "allprofiles", "list_profiles"):
        profiles = get_firewall_profiles()
        summary_text = f"Retrieved {len(profiles)} firewall profile states."
        return json.dumps({"status": "success", "summary": summary_text, "profiles": profiles}, indent=2)

    if action in ("rule", "inspect", "get_rule"):
        if not rule_name:
            return json.dumps({"status": "error", "message": "Parameter 'rule_name' is required."}, indent=2)
        rules = get_firewall_rule(rule_name)
        summary_text = f"Found {len(rules)} rule(s) matching '{rule_name}'."
        return json.dumps({"status": "success", "summary": summary_text, "rules": rules}, indent=2)

    if action in ("search", "find"):
        if not query:
            return json.dumps({"status": "error", "message": "Search parameter 'query' is required."}, indent=2)
        matches = search_firewall_rules(query, limit=limit)
        summary_text = f"Found {len(matches)} firewall rule(s) matching '{query}'."
        return json.dumps({"status": "success", "summary": summary_text, "matches": matches}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, profiles, rule, search."
    }, indent=2)


TOOL = {
    "name": "firewall_sentinel",
    "description": "Inspect Windows Defender Firewall active profile states (Domain, Private, Public), audit default packet filtering policies, and inspect firewall rules via netsh.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "profiles", "rule", "search"],
                "description": "Firewall action to execute (default: 'summary').",
            },
            "rule_name": {
                "type": "STRING",
                "description": "Exact firewall rule name to inspect.",
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword or port to find matching rules.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum search matches to return (default: 10).",
            },
        },
    },
    "handler": firewall_sentinel,
}
