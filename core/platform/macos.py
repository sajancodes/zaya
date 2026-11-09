"""macOS Platform Adapter for Zaya (Darwin).
Created and developed by Sajan Rai for Zaya.

Uses osascript (AppleScript), screencapture, and POSIX process management.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
from typing import List, Optional

from core.platform.base import PlatformAdapter, PowerStatus, WindowInfo

logger = logging.getLogger(__name__)


class MacOSAdapter(PlatformAdapter):
    """Adapter for Apple macOS systems."""

    @property
    def platform_name(self) -> str:
        return "macos"

    def show_notification(self, title: str, message: str) -> bool:
        """Display native macOS notification banner via osascript."""
        clean_title = title.replace('"', '\\"')
        clean_msg = message.replace('"', '\\"')
        script = f'display notification "{clean_msg}" with title "{clean_title}"'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
            return res.returncode == 0
        except Exception as e:
            logger.debug("[MacOSAdapter] Notification error: %s", e)
            return False

    def list_windows(self) -> List[WindowInfo]:
        """List running GUI application windows via AppleScript."""
        results: List[WindowInfo] = []
        script = """
        tell application "System Events"
            set procList to every process whose visible is true
            set winInfo to {}
            repeat with p in procList
                set pName to name of p
                set pId to unix id of p
                try
                    repeat with w in (every window of p)
                        set wTitle to name of w
                        if wTitle is not "" then
                            copy (pName & "|||" & pId & "|||" & wTitle) to end of winInfo
                        end if
                    end repeat
                end try
            end repeat
            return winInfo
        end tell
        """
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split(", "):
                    parts = line.strip().split("|||")
                    if len(parts) >= 3:
                        pname, pid_str, title = parts[0], parts[1], parts[2]
                        results.append(
                            WindowInfo(
                                id=f"mac_{pid_str}_{title[:10]}",
                                title=title,
                                process_name=pname,
                                pid=int(pid_str) if pid_str.isdigit() else None,
                                is_visible=True,
                            )
                        )
        except Exception as e:
            logger.debug("[MacOSAdapter] list_windows error: %s", e)
        return results

    def capture_screen(self, region: Optional[List[int]] = None) -> Optional[bytes]:
        """Capture screen using macOS screencapture CLI."""
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = ["screencapture", "-x", "-C"]
            if region and len(region) >= 4:
                x1, y1, x2, y2 = region[:4]
                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)
                cmd += ["-R", f"{x},{y},{w},{h}"]
            cmd.append(tmp_path)

            res = subprocess.run(cmd, capture_output=True, timeout=4)
            if res.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.unlink(tmp_path)
                return data
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception as e:
            logger.debug("[MacOSAdapter] capture_screen error: %s", e)
        return None

    def terminate_process_tree(self, pid: int, timeout_sec: float = 3.0) -> bool:
        """Terminate process tree using pkill -P on macOS."""
        try:
            # Kill children first
            subprocess.run(["pkill", "-TERM", "-P", str(pid)], capture_output=True, timeout=1)
            # Kill parent
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except Exception:
                return False

    def get_power_status(self) -> PowerStatus:
        """Inspect macOS battery using pmset -g batt."""
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                text = res.stdout.lower()
                ac = "ac power" in text
                pct = None
                import re
                m = re.search(r"(\d+)%", text)
                if m:
                    pct = int(m.group(1))
                return PowerStatus(battery_percent=pct, power_plugged=ac, power_plan="Auto")
        except Exception:
            pass
        return PowerStatus()
