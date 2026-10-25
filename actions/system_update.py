"""System Update Action for checking and installing official Zaya releases.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import threading
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.update import desktop_updater, UpdateStatus


def system_update(parameters: dict, **_kwargs) -> ToolResult:
    """Check, download, or apply official Zaya desktop updates."""
    require_owner()
    action = str(parameters.get("action") or "check").lower().strip()

    if action == "check":
        manifest = desktop_updater.check(force=True)
        if manifest:
            return ToolResult(
                "success",
                f"Zaya update available: v{manifest.version} (build {manifest.build}). Use system_update with action='download' to fetch it.",
                data={"version": manifest.version, "build": manifest.build, "status": "AVAILABLE"},
                side_effect=True
            )
        st = desktop_updater.status
        msg = desktop_updater.error_message or "Zaya is up to date."
        return ToolResult(
            "success" if st == UpdateStatus.UP_TO_DATE else "failed",
            msg,
            data={"status": st.value}
        )

    elif action == "download":
        if not desktop_updater.available_manifest:
            manifest = desktop_updater.check(force=True)
            if not manifest:
                return ToolResult("success", "No update available to download.")

        path = desktop_updater.download()
        if path and path.is_file():
            return ToolResult(
                "success",
                f"Update v{desktop_updater.available_manifest.version} downloaded and verified. Use action='apply' to restart and update.",
                data={"installer": str(path), "status": "READY"},
                side_effect=True
            )
        return ToolResult(
            "failed",
            f"Failed to download update: {desktop_updater.error_message}",
            data={"status": "FAILED"}
        )

    elif action == "apply":
        if desktop_updater.status != UpdateStatus.READY:
            return ToolResult("failed", "No verified update is ready to install. Check and download first.")
        ok = desktop_updater.apply_update(restart=True, silent=True)
        if ok:
            return ToolResult("success", "Launching Zaya installer and restarting.", side_effect=True)
        return ToolResult("failed", f"Failed to apply update: {desktop_updater.error_message}")

    elif action == "status":
        return ToolResult(
            "success",
            f"Update status: {desktop_updater.status.value}. {desktop_updater.error_message}".strip(),
            data={
                "status": desktop_updater.status.value,
                "available_version": desktop_updater.available_manifest.version if desktop_updater.available_manifest else None,
                "progress": desktop_updater.download_progress
            }
        )

    return ToolResult("failed", f"Unknown update action: {action}. Use 'check', 'download', 'apply', or 'status'.")


TOOL = {
    "name": "system_update",
    "description": (
        "Check for, download, or apply official Zaya updates. "
        "Actions: 'check' (looks for newer releases on GitHub), 'download' (downloads and cryptographically verifies installer), "
        "'apply' (restarts and updates Zaya), 'status' (reports current update state)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["check", "download", "apply", "status"],
                "description": "The update operation to execute."
            }
        }
    },
    "handler": system_update
}
