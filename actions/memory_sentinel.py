"""System Memory Leak & Process RAM Footprint Sentinel.
Created and developed by Sajan Rai for Zaya.

Analyzes physical and virtual RAM consumption, aggregates multi-process application footprints
(e.g., browsers, IDEs, language servers), and evaluates real-time memory pressure and leak indicators.
"""
from __future__ import annotations

from collections import defaultdict
import json
import logging
from typing import Any, Dict, List, Optional
import psutil

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)


def get_virtual_memory_stats() -> Dict[str, Any]:
    """Retrieve detailed physical RAM and Windows pagefile / swap telemetry."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_available_gb": round(mem.available / (1024**3), 2),
        "ram_percent": mem.percent,
        "swap_total_gb": round(swap.total / (1024**3), 2),
        "swap_used_gb": round(swap.used / (1024**3), 2),
        "swap_free_gb": round(swap.free / (1024**3), 2),
        "swap_percent": swap.percent,
    }


def get_top_memory_consumers(limit: int = 10, group_by_name: bool = True) -> List[Dict[str, Any]]:
    """Retrieve the highest RAM-consuming processes, optionally grouped by application name."""
    total_ram = psutil.virtual_memory().total

    if group_by_name:
        groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "rss": 0, "pids": []})
        for p in psutil.process_iter(["name", "memory_info", "pid"]):
            try:
                info = p.info
                name = info.get("name") or "Unknown"
                mem_info = info.get("memory_info")
                rss = mem_info.rss if mem_info else 0
                pid = info.get("pid")

                groups[name]["count"] += 1
                groups[name]["rss"] += rss
                if pid and len(groups[name]["pids"]) < 5:
                    groups[name]["pids"].append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        sorted_groups = sorted(groups.items(), key=lambda x: x[1]["rss"], reverse=True)
        results: List[Dict[str, Any]] = []

        for name, data in sorted_groups[:limit]:
            rss_mb = round(data["rss"] / (1024**2), 1)
            rss_gb = round(data["rss"] / (1024**3), 2)
            pct = round((data["rss"] / total_ram) * 100, 1) if total_ram else 0.0

            results.append({
                "application": name,
                "process_count": data["count"],
                "memory_mb": rss_mb,
                "memory_gb": rss_gb,
                "memory_percent": pct,
                "sample_pids": data["pids"],
            })

        return results

    # Individual per-PID breakdown
    procs: List[Dict[str, Any]] = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = p.info
            mem_info = info.get("memory_info")
            rss = mem_info.rss if mem_info else 0
            procs.append({
                "pid": info.get("pid"),
                "name": info.get("name") or "Unknown",
                "rss": rss,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    sorted_procs = sorted(procs, key=lambda x: x["rss"], reverse=True)
    results_indiv: List[Dict[str, Any]] = []
    for pr in sorted_procs[:limit]:
        rss_mb = round(pr["rss"] / (1024**2), 1)
        rss_gb = round(pr["rss"] / (1024**3), 2)
        pct = round((pr["rss"] / total_ram) * 100, 1) if total_ram else 0.0
        results_indiv.append({
            "pid": pr["pid"],
            "application": pr["name"],
            "memory_mb": rss_mb,
            "memory_gb": rss_gb,
            "memory_percent": pct,
        })

    return results_indiv


def assess_memory_pressure() -> Dict[str, Any]:
    """Evaluate system memory pressure, low-RAM thresholds, and heavy workloads."""
    stats = get_virtual_memory_stats()
    top_apps = get_top_memory_consumers(limit=5, group_by_name=True)

    ram_pct = stats["ram_percent"]
    avail_gb = stats["ram_available_gb"]
    swap_pct = stats["swap_percent"]

    if ram_pct >= 88.0 or avail_gb < 1.5 or swap_pct >= 80.0:
        pressure_level = "Critical (High memory saturation / thrashing risk)"
        status_code = "critical"
    elif ram_pct >= 75.0 or avail_gb < 3.0:
        pressure_level = "Elevated (Moderate memory load)"
        status_code = "elevated"
    else:
        pressure_level = "Healthy (Substantial available memory)"
        status_code = "healthy"

    dominant_app = top_apps[0] if top_apps else None

    return {
        "status": "success",
        "pressure_level": pressure_level,
        "status_code": status_code,
        "stats": stats,
        "dominant_application": dominant_app,
        "top_applications": top_apps,
    }


def memory_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches RAM inspection, process memory aggregation, and pressure audits."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    limit = int(parameters.get("limit") or 10)
    group = bool(parameters.get("group_by_name", True))

    if action in ("summary", "health", "pressure"):
        assessment = assess_memory_pressure()
        stats = assessment["stats"]
        dom = assessment.get("dominant_application")
        dom_note = f" Top consumer: {dom['application']} ({dom['memory_mb']:,} MB across {dom['process_count']} procs)." if dom else ""
        summary_text = (
            f"RAM Status: {assessment['pressure_level']}. "
            f"Used: {stats['ram_used_gb']} GB / {stats['ram_total_gb']} GB ({stats['ram_percent']}%, {stats['ram_available_gb']} GB available). "
            f"Pagefile: {stats['swap_used_gb']} GB / {stats['swap_total_gb']} GB ({stats['swap_percent']}%).{dom_note}"
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": assessment}, indent=2)

    if action in ("stats", "virtual_memory"):
        stats = get_virtual_memory_stats()
        summary_text = f"Physical RAM: {stats['ram_used_gb']} GB / {stats['ram_total_gb']} GB ({stats['ram_percent']}%). Pagefile: {stats['swap_percent']}%."
        return json.dumps({"status": "success", "summary": summary_text, "stats": stats}, indent=2)

    if action in ("top_processes", "top_apps", "apps", "processes"):
        top = get_top_memory_consumers(limit=limit, group_by_name=group)
        summary_text = f"Retrieved top {len(top)} memory-consuming applications."
        return json.dumps({"status": "success", "summary": summary_text, "top_consumers": top}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, stats, top_processes."
    }, indent=2)


TOOL = {
    "name": "memory_sentinel",
    "description": "Inspect physical RAM and virtual pagefile memory, aggregate process footprints by application name (e.g., browsers, IDEs), and evaluate memory pressure.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "stats", "top_processes"],
                "description": "Memory action to execute (default: 'summary').",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of top memory consumers to retrieve (default: 10).",
            },
            "group_by_name": {
                "type": "BOOLEAN",
                "description": "Consolidate multi-process apps into single entries (default: true).",
            },
        },
    },
    "handler": memory_sentinel,
}
