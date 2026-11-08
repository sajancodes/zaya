"""Storage Sentinel & System Disk Waste Analyzer.
Created and developed by Sajan Rai for Zaya.

Provides real-time partition storage telemetry, safe temporary junk analysis,
safe cache pruning (older than specified age), and large file discovery with
strict owner verification and filesystem guardrails.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional

import psutil

from core.execution_policy import require_owner


def _get_drive_telemetry() -> List[Dict[str, Any]]:
    """Return storage metrics across all active local disk partitions."""
    results = []
    for part in psutil.disk_partitions(all=False):
        # Focus on fixed/local drives
        if "cdrom" in part.opts or part.fstype == "":
            continue
        try:
            usage = shutil.disk_usage(part.mountpoint)
            total_gb = round(usage.total / (1024**3), 2)
            used_gb = round(usage.used / (1024**3), 2)
            free_gb = round(usage.free / (1024**3), 2)
            pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0

            results.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "used_percent": pct,
            })
        except (PermissionError, OSError):
            continue
    return results


def _scan_temp_waste(max_age_hours: int = 24) -> Dict[str, Any]:
    """Scan user temp directory for files older than max_age_hours."""
    temp_dir = Path(tempfile.gettempdir())
    now = time.time()
    cutoff_time = now - (max_age_hours * 3600)

    total_scanned = 0
    safe_files = 0
    reclaimable_bytes = 0

    try:
        for entry in temp_dir.rglob("*"):
            if entry.is_file():
                total_scanned += 1
                try:
                    stat = entry.stat()
                    if stat.st_mtime < cutoff_time:
                        safe_files += 1
                        reclaimable_bytes += stat.st_size
                except (PermissionError, OSError):
                    continue
            if total_scanned >= 5000:
                break
    except (PermissionError, OSError):
        pass

    reclaimable_mb = round(reclaimable_bytes / (1024 * 1024), 2)
    return {
        "temp_path": str(temp_dir),
        "total_files_scanned": total_scanned,
        "stale_files_found": safe_files,
        "reclaimable_mb": reclaimable_mb,
        "max_age_hours": max_age_hours,
    }


def _clean_temp_waste(max_age_hours: int = 24) -> Dict[str, Any]:
    """Safely purge temporary files older than max_age_hours."""
    temp_dir = Path(tempfile.gettempdir())
    now = time.time()
    cutoff_time = now - (max_age_hours * 3600)

    deleted_count = 0
    freed_bytes = 0
    skipped_count = 0

    try:
        for entry in temp_dir.rglob("*"):
            if entry.is_file():
                try:
                    stat = entry.stat()
                    if stat.st_mtime < cutoff_time:
                        size = stat.st_size
                        entry.unlink()
                        deleted_count += 1
                        freed_bytes += size
                    else:
                        skipped_count += 1
                except (PermissionError, OSError):
                    skipped_count += 1
            if deleted_count >= 2000:
                break
    except (PermissionError, OSError):
        pass

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    return {
        "temp_path": str(temp_dir),
        "deleted_count": deleted_count,
        "skipped_count": skipped_count,
        "freed_mb": freed_mb,
    }


def _find_large_files(search_dir: Optional[str] = None, min_size_mb: int = 200, limit: int = 10) -> List[Dict[str, Any]]:
    """Locate files exceeding min_size_mb in a safe user directory."""
    if not search_dir:
        # Default to user home downloads / documents
        search_path = Path.home() / "Downloads"
        if not search_path.exists():
            search_path = Path.home()
    else:
        search_path = Path(search_dir).resolve()

    min_bytes = min_size_mb * 1024 * 1024
    large_files = []

    try:
        for root, dirs, files in os.walk(search_path):
            # Skip hidden, git, and system directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("AppData", "node_modules", "Windows", "Program Files")]
            for f in files:
                f_path = Path(root) / f
                try:
                    size = f_path.stat().st_size
                    if size >= min_bytes:
                        large_files.append({
                            "name": f,
                            "path": str(f_path),
                            "size_mb": round(size / (1024 * 1024), 2),
                        })
                except (PermissionError, OSError):
                    continue
                if len(large_files) >= 50:
                    break
            if len(large_files) >= 50:
                break
    except Exception:
        pass

    large_files.sort(key=lambda x: x["size_mb"], reverse=True)
    return large_files[:limit]


def storage_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches disk space inspection, temp cleanup, and large file analysis."""
    require_owner()
    action = str(parameters.get("action") or "free_space").lower().strip()

    # 1. Free Space / Drive Telemetry
    if action in ("free_space", "space", "status", "drives"):
        drives = _get_drive_telemetry()
        if not drives:
            return json.dumps({"status": "error", "message": "Unable to read storage partitions."}, indent=2)

        summary_parts = []
        for d in drives:
            summary_parts.append(f"{d['mountpoint']} has {d['free_gb']} GB free out of {d['total_gb']} GB ({d['used_percent']}% used)")
        summary = "Disk Space: " + "; ".join(summary_parts) + "."
        return json.dumps({"status": "success", "summary": summary, "data": drives}, indent=2)

    # 2. Analyze Temp Waste
    if action in ("analyze_junk", "scan", "analyze"):
        max_age = int(parameters.get("max_age_hours") or 24)
        waste = _scan_temp_waste(max_age)
        summary = (
            f"Temp Storage Analysis: Found {waste['stale_files_found']} stale files "
            f"({waste['reclaimable_mb']} MB reclaimable) older than {max_age} hours in '{waste['temp_path']}'."
        )
        return json.dumps({"status": "success", "summary": summary, "data": waste}, indent=2)

    # 3. Clean Temp Waste
    if action in ("clean_junk", "clean", "purge"):
        max_age = int(parameters.get("max_age_hours") or 24)
        cleaned = _clean_temp_waste(max_age)
        summary = (
            f"Cleaned {cleaned['deleted_count']} temporary file(s), "
            f"reclaiming {cleaned['freed_mb']} MB from '{cleaned['temp_path']}'."
        )
        return json.dumps({"status": "success", "summary": summary, "data": cleaned}, indent=2)

    # 4. Large Files Discovery
    if action in ("large_files", "large"):
        min_mb = int(parameters.get("min_size_mb") or 200)
        limit = max(1, min(int(parameters.get("limit") or 10), 30))
        target_dir = parameters.get("directory")
        large = _find_large_files(target_dir, min_size_mb=min_mb, limit=limit)
        if large:
            summary = f"Found {len(large)} file(s) exceeding {min_mb} MB: " + ", ".join(f"{f['name']} ({f['size_mb']} MB)" for f in large[:3])
        else:
            summary = f"No files exceeding {min_mb} MB found in target directory."
        return json.dumps({"status": "success", "summary": summary, "data": large}, indent=2)

    # 5. Full Storage Health Summary
    if action == "summary":
        drives = _get_drive_telemetry()
        waste = _scan_temp_waste(24)
        primary = drives[0] if drives else {"free_gb": "Unknown", "total_gb": "Unknown"}
        summary = (
            f"Storage Health: Primary drive {primary.get('mountpoint', 'C:')} has {primary.get('free_gb')} GB free "
            f"out of {primary.get('total_gb')} GB. Temp cache has {waste['reclaimable_mb']} MB safe to clean."
        )
        return json.dumps({"status": "success", "summary": summary, "data": {"drives": drives, "waste": waste}}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: free_space, analyze_junk, clean_junk, large_files, summary."
    }, indent=2)


TOOL = {
    "name": "storage_sentinel",
    "description": "Inspect partition storage capacity, analyze stale temporary cache waste, discover oversized files, and safely reclaim disk space.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["free_space", "analyze_junk", "clean_junk", "large_files", "summary"],
                "description": "Storage action to perform (default: 'free_space').",
            },
            "max_age_hours": {
                "type": "INTEGER",
                "description": "Age threshold in hours for safe temporary file deletion (default: 24).",
            },
            "min_size_mb": {
                "type": "INTEGER",
                "description": "Minimum file size in MB for large file search (default: 200).",
            },
            "directory": {
                "type": "STRING",
                "description": "Optional directory path to scan for large files.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of large files to return (default: 10).",
            },
        },
    },
    "handler": storage_sentinel,
}
