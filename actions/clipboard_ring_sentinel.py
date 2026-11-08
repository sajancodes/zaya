"""Windows Clipboard History & Multi-Item Ring Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects and controls Windows native Clipboard History (Win + V) and cloud clipboard
synchronization state via HKCU\\Software\\Microsoft\\Clipboard.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
import winreg

from core.execution_policy import require_owner


_CLIPBOARD_REG_PATH = r"Software\Microsoft\Clipboard"


def get_clipboard_history_status() -> Dict[str, Any]:
    """Inspect Windows native Clipboard History and cloud sync state."""
    if os.name != "nt":
        return {
            "status": "unavailable",
            "enabled": False,
            "cloud_sync": False,
            "hotkey": "Win + V",
            "message": "Windows Clipboard History is only available on Windows 10/11.",
        }

    enabled = False
    cloud_sync = False
    shell_hotkey_used = False

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CLIPBOARD_REG_PATH) as k:
            try:
                val, _ = winreg.QueryValueEx(k, "EnableClipboardHistory")
                enabled = bool(val == 1)
            except FileNotFoundError:
                enabled = False

            try:
                val, _ = winreg.QueryValueEx(k, "CloudClipboardAutomaticUpload")
                cloud_sync = bool(val == 1)
            except FileNotFoundError:
                cloud_sync = False

            try:
                val, _ = winreg.QueryValueEx(k, "ShellHotKeyUsed")
                shell_hotkey_used = bool(val == 1)
            except FileNotFoundError:
                pass

        return {
            "status": "success",
            "enabled": enabled,
            "cloud_sync": cloud_sync,
            "shell_hotkey_used": shell_hotkey_used,
            "hotkey": "Win + V",
            "state_label": "Enabled" if enabled else "Disabled",
        }
    except Exception as e:
        return {
            "status": "error",
            "enabled": False,
            "cloud_sync": False,
            "hotkey": "Win + V",
            "message": f"Failed to query Windows Clipboard settings: {e}",
        }


def set_clipboard_history(enabled: bool) -> Dict[str, Any]:
    """Enable or disable Windows native Clipboard History (Win + V)."""
    if os.name != "nt":
        return {"status": "unavailable", "message": "Requires Windows 10/11."}

    val = 1 if enabled else 0
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CLIPBOARD_REG_PATH) as k:
            winreg.SetValueEx(k, "EnableClipboardHistory", 0, winreg.REG_DWORD, val)

        state_txt = "enabled" if enabled else "disabled"
        return {
            "status": "success",
            "enabled": enabled,
            "message": f"Windows Clipboard History has been {state_txt} (Win + V).",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to set Clipboard History: {e}"}


def toggle_clipboard_history() -> Dict[str, Any]:
    """Toggle current Windows native Clipboard History state."""
    cur = get_clipboard_history_status()
    if cur["status"] not in ("success", "active"):
        return {"status": "error", "message": cur.get("message", "Unable to toggle Clipboard History.")}
    return set_clipboard_history(not cur["enabled"])


def clipboard_ring_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and toggling Windows Clipboard History."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()

    if action in ("status", "summary"):
        info = get_clipboard_history_status()
        if info.get("status") == "error":
            return json.dumps(info, indent=2)

        sync_str = ", Cloud Sync ON" if info.get("cloud_sync") else ""
        summary = f"Windows Clipboard History: {info['state_label']} (Hotkey: {info['hotkey']}{sync_str})."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": info,
        }, indent=2)

    if action in ("enable", "on", "activate"):
        res = set_clipboard_history(True)
        return json.dumps(res, indent=2)

    if action in ("disable", "off", "deactivate"):
        res = set_clipboard_history(False)
        return json.dumps(res, indent=2)

    if action in ("toggle", "switch"):
        res = toggle_clipboard_history()
        return json.dumps(res, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, enable, disable, toggle.",
    }, indent=2)


TOOL = {
    "name": "clipboard_ring_sentinel",
    "description": "Inspect and toggle Windows native Clipboard History (Win + V) and cloud clipboard synchronization.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "enable", "disable", "toggle"],
                "description": "Clipboard history action to perform (default: 'status').",
            },
        },
    },
    "handler": clipboard_ring_sentinel,
}
