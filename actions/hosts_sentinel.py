"""Windows Hosts File & Local Domain Override Sentinel.
Created and developed by Sajan Rai for Zaya.

Parses, audits, and searches local domain-to-IP overrides in C:\\Windows\\System32\\drivers\\etc\\hosts
for local development endpoints, loopback mappings, and custom domain routing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


def _get_hosts_path() -> Path:
    """Return platform-specific hosts file path."""
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        return Path(system_root) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def parse_hosts_file() -> List[Dict[str, Any]]:
    """Parse active IP-to-domain mappings from the hosts file."""
    path = _get_hosts_path()
    if not path.exists():
        return []

    mappings: List[Dict[str, Any]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue

            comment = ""
            if "#" in clean:
                parts = clean.split("#", 1)
                clean = parts[0].strip()
                comment = parts[1].strip()

            tokens = clean.split()
            if len(tokens) >= 2:
                ip = tokens[0]
                domains = tokens[1:]
                for domain in domains:
                    # Categorize entry
                    cat = "Custom"
                    d_low = domain.lower()
                    if any(d_low.endswith(sfx) for sfx in (".local", ".test", ".dev", ".localhost")):
                        cat = "Local Development"
                    elif comment and any(kw in comment.lower() for kw in ("block", "fake", "ad", "track")):
                        cat = "Security / Filter"
                    elif ip in ("127.0.0.1", "::1") or d_low == "localhost":
                        cat = "Loopback"

                    mappings.append({
                        "ip": ip,
                        "domain": domain,
                        "category": cat,
                        "comment": comment or None,
                    })
    except Exception:
        pass

    return mappings


def search_hosts(query: str) -> List[Dict[str, Any]]:
    """Search for domain names or IP addresses in hosts mappings."""
    clean_q = query.strip().lower()
    all_maps = parse_hosts_file()
    return [
        m for m in all_maps
        if clean_q in m["domain"].lower() or clean_q in m["ip"]
    ]


def get_hosts_summary() -> Dict[str, Any]:
    """Generate high-level audit of hosts file overrides."""
    mappings = parse_hosts_file()
    total = len(mappings)

    loopback_count = sum(1 for m in mappings if m["category"] in ("Loopback", "Local Development"))
    filter_count = sum(1 for m in mappings if m["category"] == "Security / Filter")
    custom_count = total - loopback_count - filter_count

    sample = [f"{m['domain']} -> {m['ip']}" for m in mappings[:6]]

    return {
        "status": "success",
        "hosts_path": str(_get_hosts_path()),
        "total_mappings": total,
        "local_dev_mappings": loopback_count,
        "filter_mappings": filter_count,
        "custom_mappings": custom_count,
        "sample_entries": sample,
    }


def hosts_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and searching hosts file mappings."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "summary").lower().strip()

    if action in ("summary", "status"):
        summary = get_hosts_summary()
        sample_str = ", ".join(summary["sample_entries"]) if summary["sample_entries"] else "None"
        summary_text = (
            f"Hosts File Audit ({summary['hosts_path']}): {summary['total_mappings']} active mapping(s). "
            f"Local dev/loopback: {summary['local_dev_mappings']}, Filtered: {summary['filter_mappings']}. "
            f"Sample: {sample_str}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary_text,
            "data": summary,
        }, indent=2)

    if action in ("lookup", "search", "check"):
        query = params.get("domain") or params.get("query") or params.get("ip")
        if not query:
            return json.dumps({
                "status": "error",
                "message": "Must provide 'domain' or 'query' to search in hosts file."
            }, indent=2)

        matches = search_hosts(str(query))
        found = len(matches) > 0
        summary_text = f"Found {len(matches)} matching mapping(s) for '{query}' in hosts file."
        return json.dumps({
            "status": "success" if found else "not_found",
            "summary": summary_text,
            "data": {"matches": matches},
        }, indent=2)

    if action in ("list", "all"):
        mappings = parse_hosts_file()
        return json.dumps({
            "status": "success",
            "summary": f"Hosts file has {len(mappings)} active mapping(s).",
            "data": {"count": len(mappings), "mappings": mappings[:100]},
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, lookup, list.",
    }, indent=2)


TOOL = {
    "name": "hosts_sentinel",
    "description": "Inspect and search the Windows hosts file (C:\\Windows\\System32\\drivers\\etc\\hosts): audit local development domain mappings, loopback overrides, and security block rules.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "lookup", "list"],
                "description": "Hosts inspection action (default: 'summary').",
            },
            "domain": {
                "type": "STRING",
                "description": "Domain name or IP to search when action is 'lookup'.",
            },
        },
    },
    "handler": hosts_sentinel,
}
