"""Linux Platform Adapter for Zaya (X11 & Wayland).
Created and developed by Sajan Rai for Zaya.

Handles X11 vs Wayland isolation, notify-send, scrot/grim, and POSIX process control.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
from typing import List, Optional

from core.platform.base import PlatformAdapter, PowerStatus, WindowInfo

logger = logging.getLogger(__name__)


class LinuxAdapter(PlatformAdapter):
    """Adapter for Linux systems (X11 and Wayland)."""

    @property
    def platform_name(self) -> str:
        return "linux"

    def is_wayland(self) -> bool:
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        return "wayland" in session or bool(os.environ.get("WAYLAND_DISPLAY"))

    def show_notification(self, title: str, message: str) -> bool:
        """Display native desktop notification using notify-send."""
        try:
            res = subprocess.run(
                ["notify-send", "-a", "Zaya", title, message],
                capture_output=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception as e:
            logger.debug("[LinuxAdapter] notify-send error: %s", e)
            return False

    def list_windows(self) -> List[WindowInfo]:
        """List active desktop windows.

        Note: On Wayland, global window inspection is security-restricted by design
        unless xdg-desktop-portal or compositor-specific protocols are permitted.
        On X11, wmctrl or xdotool are used.
        """
        results: List[WindowInfo] = []
        if self.is_wayland():
            logger.debug("[LinuxAdapter] Global window listing restricted by Wayland security policy.")
            return results

        # X11 fallback using wmctrl
        try:
            res = subprocess.run(["wmctrl", "-l", "-p"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = line.split(maxsplit=4)
                    if len(parts) >= 5:
                        wid, desktop_num, pid_str, client, title = parts
                        results.append(
                            WindowInfo(
                                id=wid,
                                title=title,
                                process_name=client,
                                pid=int(pid_str) if pid_str.isdigit() else None,
                                is_visible=True,
                            )
                        )
        except Exception as e:
            logger.debug("[LinuxAdapter] wmctrl error: %s", e)
        return results

    def capture_screen(self, region: Optional[List[int]] = None) -> Optional[bytes]:
        """Capture screen using grim (Wayland) or scrot (X11)."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if self.is_wayland():
                # Wayland capture using grim
                cmd = ["grim"]
                if region and len(region) >= 4:
                    x1, y1, x2, y2 = region[:4]
                    x = min(x1, x2)
                    y = min(y1, y2)
                    w = abs(x2 - x1)
                    h = abs(y2 - y1)
                    cmd += ["-g", f"{x},{y} {w}x{h}"]
                cmd.append(tmp_path)
            else:
                # X11 capture using scrot
                cmd = ["scrot", "-z"]
                if region and len(region) >= 4:
                    x1, y1, x2, y2 = region[:4]
                    x = min(x1, x2)
                    y = min(y1, y2)
                    w = abs(x2 - x1)
                    h = abs(y2 - y1)
                    cmd += ["-a", f"{x},{y},{w},{h}"]
                cmd.append(tmp_path)

            res = subprocess.run(cmd, capture_output=True, timeout=4)
            if res.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.unlink(tmp_path)
                return data
        except Exception as e:
            logger.debug("[LinuxAdapter] capture error: %s", e)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        return None

    def terminate_process_tree(self, pid: int, timeout_sec: float = 3.0) -> bool:
        """Terminate process tree using pkill -P on Linux."""
        try:
            subprocess.run(["pkill", "-TERM", "-P", str(pid)], capture_output=True, timeout=1)
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except Exception:
                return False

    def get_power_status(self) -> PowerStatus:
        """Inspect power status via /sys/class/power_supply/."""
        try:
            bat_dir = "/sys/class/power_supply/BAT0"
            if os.path.exists(bat_dir):
                cap_file = os.path.join(bat_dir, "capacity")
                stat_file = os.path.join(bat_dir, "status")
                pct = None
                plugged = None
                if os.path.exists(cap_file):
                    pct = int(open(cap_file).read().strip())
                if os.path.exists(stat_file):
                    plugged = open(stat_file).read().strip().lower() in {"charging", "full"}
                return PowerStatus(battery_percent=pct, power_plugged=plugged, power_plan="Linux Default")
        except Exception:
            pass
        return PowerStatus()
