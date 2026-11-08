"""Windows Recycle Bin & Storage Trash Sentinel.
Created and developed by Sajan Rai for Zaya.

Audits deleted items and disk space consumed by the Windows Recycle Bin
across drive volumes and empties trash safely via pure Win32 shell32 APIs.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from typing import Any, Dict, Optional

from core.execution_policy import require_owner


# Win32 flags for SHEmptyRecycleBinW
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


def get_recycle_bin_stats(drive: Optional[str] = None) -> Dict[str, Any]:
    """Query item count and total size in bytes of the Windows Recycle Bin."""
    if os.name != "nt":
        return {
            "status": "unavailable",
            "items_count": 0,
            "size_bytes": 0,
            "size_mb": 0.0,
            "size_gb": 0.0,
            "drive": drive or "All Drives",
            "is_empty": True,
        }

    clean_drive = drive.strip() if drive else None
    if clean_drive and not clean_drive.endswith("\\"):
        clean_drive = f"{clean_drive}\\"

    try:
        rb = _SHQUERYRBINFO()
        rb.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        shell32 = ctypes.windll.shell32
        hr = shell32.SHQueryRecycleBinW(clean_drive, ctypes.byref(rb))
        if hr != 0:
            return {
                "status": "error",
                "message": f"SHQueryRecycleBinW failed with code {hr:#x}",
                "items_count": 0,
                "size_bytes": 0,
                "size_mb": 0.0,
                "size_gb": 0.0,
                "drive": clean_drive or "All Drives",
                "is_empty": True,
            }

        num_items = int(rb.i64NumItems)
        total_bytes = int(rb.i64Size)
        mb = round(total_bytes / (1024 * 1024), 2)
        gb = round(total_bytes / (1024 * 1024 * 1024), 3)

        return {
            "status": "success",
            "items_count": num_items,
            "size_bytes": total_bytes,
            "size_mb": mb,
            "size_gb": gb,
            "drive": clean_drive or "All Drives",
            "is_empty": (num_items == 0),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to query Recycle Bin: {e}",
            "items_count": 0,
            "size_bytes": 0,
            "size_mb": 0.0,
            "size_gb": 0.0,
            "drive": clean_drive or "All Drives",
            "is_empty": True,
        }


def empty_recycle_bin(drive: Optional[str] = None) -> Dict[str, Any]:
    """Empty the Windows Recycle Bin without UI prompts or interruptions."""
    if os.name != "nt":
        return {"status": "unavailable", "message": "Recycle Bin operations require Windows."}

    # Record previous size to announce freed space
    prev = get_recycle_bin_stats(drive)

    clean_drive = drive.strip() if drive else None
    if clean_drive and not clean_drive.endswith("\\"):
        clean_drive = f"{clean_drive}\\"

    try:
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        shell32 = ctypes.windll.shell32
        hr = shell32.SHEmptyRecycleBinW(None, clean_drive, flags)

        # hr == 0 (S_OK) or hr == 0x80004005 (already empty)
        freed_mb = prev.get("size_mb", 0.0)
        items_freed = prev.get("items_count", 0)

        return {
            "status": "success",
            "freed_items": items_freed,
            "freed_bytes": prev.get("size_bytes", 0),
            "freed_mb": freed_mb,
            "message": f"Emptied Recycle Bin. Removed {items_freed} item(s) and freed {freed_mb} MB.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to empty Recycle Bin: {e}"}


def recycle_bin_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and clearing the Windows Recycle Bin."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()
    drive = params.get("drive")

    if action in ("status", "summary"):
        stats = get_recycle_bin_stats(drive)
        if stats.get("status") == "error":
            return json.dumps(stats, indent=2)

        if stats["is_empty"]:
            summary = f"Recycle Bin ({stats['drive']}) is completely empty, sir."
        else:
            summary = (
                f"Recycle Bin ({stats['drive']}): {stats['items_count']:,} item(s) "
                f"occupying {stats['size_mb']:,} MB ({stats['size_gb']} GB)."
            )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": stats,
        }, indent=2)

    if action in ("empty", "clear", "purge"):
        res = empty_recycle_bin(drive)
        return json.dumps(res, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, empty.",
    }, indent=2)


TOOL = {
    "name": "recycle_bin_sentinel",
    "description": "Inspect and empty the Windows Recycle Bin: check deleted item counts, compute total disk space occupied across drives, and clear trash without UI prompts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "empty"],
                "description": "Recycle Bin action to perform (default: 'status').",
            },
            "drive": {
                "type": "STRING",
                "description": "Specific drive root to inspect or empty (e.g. 'C:\\'). Leave omitted for all drives.",
            },
        },
    },
    "handler": recycle_bin_sentinel,
}
