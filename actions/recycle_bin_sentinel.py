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
                "is_empty": False,
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
            "is_empty": False,
        }


def empty_recycle_bin(drive: Optional[str] = None, confirm: bool = False) -> Dict[str, Any]:
    """Empty the Windows Recycle Bin, validating HRESULT and confirming destructive action."""
    if os.name != "nt":
        return {"status": "unavailable", "message": "Recycle Bin operations require Windows."}

    # Record previous size to announce freed space
    prev = get_recycle_bin_stats(drive)
    if prev.get("status") == "error":
        return {"status": "error", "message": f"Cannot inspect Recycle Bin: {prev.get('message')}"}

    if prev.get("is_empty"):
        return {
            "status": "success",
            "freed_items": 0,
            "freed_bytes": 0,
            "freed_mb": 0.0,
            "message": "Recycle Bin is already empty.",
        }

    # Destructive operation safety confirmation
    if not confirm:
        return {
            "status": "confirmation_required",
            "message": (
                f"Confirmation required: Emptying the Recycle Bin permanently deletes "
                f"{prev.get('items_count', 0)} item(s) ({prev.get('size_mb', 0)} MB). Pass confirm=True to proceed."
            ),
            "items_count": prev.get("items_count", 0),
            "size_mb": prev.get("size_mb", 0.0),
        }

    clean_drive = drive.strip() if drive else None
    if clean_drive and not clean_drive.endswith("\\"):
        clean_drive = f"{clean_drive}\\"

    try:
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        shell32 = ctypes.windll.shell32
        hr = shell32.SHEmptyRecycleBinW(None, clean_drive, flags)

        unsigned_hr = (hr & 0xFFFFFFFF) if hr is not None else 0
        if unsigned_hr == 0x80004004:
            return {"status": "cancelled", "message": "Recycle Bin emptying was cancelled by user."}
        if unsigned_hr == 0x80070005:
            return {"status": "error", "message": "Permission denied: access denied to empty Recycle Bin."}
        if unsigned_hr != 0:
            return {"status": "error", "message": f"SHEmptyRecycleBinW failed with HRESULT {unsigned_hr:#x}."}

        # Post-empty verification
        post = get_recycle_bin_stats(drive)
        if post.get("status") != "success":
            return {
                "status": "unverified",
                "message": f"Empty command executed, but post-operation verification failed: {post.get('message', 'Unknown error')}",
                "freed_items": None,
                "freed_bytes": None,
                "freed_mb": None,
                "post_verification": post,
            }

        prev_items = prev.get("items_count", 0)
        prev_bytes = prev.get("size_bytes", 0)
        post_items = post.get("items_count", 0)
        post_bytes = post.get("size_bytes", 0)

        items_freed = max(0, prev_items - post_items)
        bytes_freed = max(0, prev_bytes - post_bytes)
        freed_mb = round(bytes_freed / (1024 * 1024), 2)

        if post_items > 0:
            return {
                "status": "partial_success",
                "freed_items": items_freed,
                "freed_bytes": bytes_freed,
                "freed_mb": freed_mb,
                "remaining_items": post_items,
                "remaining_bytes": post_bytes,
                "remaining_mb": post.get("size_mb", 0.0),
                "message": f"Partially emptied Recycle Bin: removed {items_freed} item(s) ({freed_mb} MB freed), {post_items} item(s) remain in use or locked.",
            }

        return {
            "status": "success",
            "freed_items": items_freed,
            "freed_bytes": bytes_freed,
            "freed_mb": freed_mb,
            "remaining_items": 0,
            "remaining_bytes": 0,
            "remaining_mb": 0.0,
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
        confirm = bool(params.get("confirm", False))
        res = empty_recycle_bin(drive, confirm=confirm)
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
            "confirm": {
                "type": "BOOLEAN",
                "description": "Must be set to true to execute destructive clearing of the Recycle Bin.",
            },
        },
    },
    "handler": recycle_bin_sentinel,
}
