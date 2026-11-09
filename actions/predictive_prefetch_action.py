"""Predictive Workspace Pre-fetcher Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.predictive_prefetch import get_prefetcher


def handle_predictive_prefetch(action: str = "status", key: str = "", tag: str = "") -> str:
    """Query, invalidate, or prefetch hot workspace diagnostic cache entries."""
    prefetcher = get_prefetcher()

    if action == "status":
        stats = prefetcher.get_stats()
        return json.dumps({"status": "success", "diagnostics": stats})

    elif action == "get":
        if not key:
            return "Error: key is required for get."
        val = prefetcher.get(key)
        return json.dumps({"status": "success", "key": key, "value": val})

    elif action == "prefetch":
        if key:
            val = prefetcher.refresh_sync(key)
            return json.dumps({"status": "success", "refreshed_key": key, "value": val})
        else:
            all_vals = prefetcher.prefetch_all()
            return json.dumps({"status": "success", "refreshed_count": len(all_vals), "data": all_vals})

    elif action == "invalidate":
        if tag:
            count = prefetcher.invalidate_tag(tag)
            return json.dumps({"status": "success", "invalidated_tag": tag, "count": count})
        elif key:
            prefetcher.set(key, None, ttl=0.0)
            return json.dumps({"status": "success", "invalidated_key": key})
        else:
            return "Error: provide either key or tag to invalidate."

    return f"Unknown prefetch action: '{action}'."


TOOL = {
    "name": "predictive_prefetch",
    "description": (
        "Inspect and control hot in-memory cached diagnostic states (git branch, workspace status, system pressure). "
        "Allows sub-millisecond retrieval of common environment status."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "get", "prefetch", "invalidate"],
                "description": "Prefetch operation to execute.",
            },
            "key": {
                "type": "STRING",
                "description": "Specific cache key (e.g. 'git_status', 'system_pressure', 'active_branch').",
            },
            "tag": {
                "type": "STRING",
                "description": "Tag group to invalidate (e.g. 'git', 'system', 'workspace').",
            },
        },
        "required": ["action"],
    },
    "handler": handle_predictive_prefetch,
}
