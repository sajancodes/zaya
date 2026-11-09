"""Windows Platform Adapter for Zaya (Windows 10/11).
Created and developed by Sajan Rai for Zaya.

Uses Win32 APIs, PowerShell, and taskkill without breaking any existing Windows features.
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import List, Optional

from core.platform.base import PlatformAdapter, PowerStatus, WindowInfo

logger = logging.getLogger(__name__)


class WindowsAdapter(PlatformAdapter):
    """Adapter for native Windows 10 and 11 systems."""

    @property
    def platform_name(self) -> str:
        return "windows"

    def show_notification(self, title: str, message: str) -> bool:
        """Display Windows toast notification via PowerShell or notify-py."""
        clean_title = title.replace('"', '`"').replace("'", "''")
        clean_msg = message.replace('"', '`"').replace("'", "''")
        ps_cmd = (
            f"[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
            f"$obj = New-Object System.Windows.Forms.NotifyIcon; "
            f"$obj.Icon = [System.Drawing.SystemIcons]::Information; "
            f"$obj.BalloonTipTitle = '{clean_title}'; "
            f"$obj.BalloonTipText = '{clean_msg}'; "
            f"$obj.Visible = $True; "
            f"$obj.ShowBalloonTip(3000)"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except Exception as e:
            logger.debug("[WindowsAdapter] Notification error: %s", e)
            return False

    def list_windows(self) -> List[WindowInfo]:
        """List active desktop windows using user32 via ctypes."""
        results: List[WindowInfo] = []
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def enum_windows_proc(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.strip()

                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = max(0, rect.right - rect.left)
                        h = max(0, rect.bottom - rect.top)

                        if title and w > 50 and h > 50:
                            results.append(
                                WindowInfo(
                                    id=str(int(hwnd)),
                                    title=title,
                                    process_name="",
                                    pid=pid.value,
                                    x=rect.left,
                                    y=rect.top,
                                    width=w,
                                    height=h,
                                    is_visible=True,
                                )
                            )
                return True

            user32.EnumWindows(enum_windows_proc, 0)
        except Exception as e:
            logger.debug("[WindowsAdapter] Win32 enum windows error: %s", e)
        return results

    def capture_screen(self, region: Optional[List[int]] = None) -> Optional[bytes]:
        """Capture screen using mss."""
        try:
            import mss
            import mss.tools
            mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
            with mss_cls() as sct:
                monitors = sct.monitors
                target = monitors[1] if len(monitors) > 1 else monitors[0]
                if region and len(region) >= 4:
                    x1, y1, x2, y2 = region[:4]
                    monitor = {
                        "left": int(min(x1, x2)),
                        "top": int(min(y1, y2)),
                        "width": max(1, int(abs(x2 - x1))),
                        "height": max(1, int(abs(y2 - y1))),
                    }
                else:
                    monitor = target
                shot = sct.grab(monitor)
                return mss.tools.to_png(shot.rgb, shot.size)
        except Exception as e:
            logger.debug("[WindowsAdapter] Screen capture error: %s", e)
            return None

    def terminate_process_tree(self, pid: int, timeout_sec: float = 3.0) -> bool:
        """Terminate tree using taskkill /F /T."""
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=timeout_sec,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return res.returncode == 0
        except Exception:
            return False

    def get_power_status(self) -> PowerStatus:
        """Inspect battery status using ctypes GetSystemPowerStatus."""
        try:
            import ctypes
            from ctypes import wintypes

            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", wintypes.BYTE),
                    ("BatteryFlag", wintypes.BYTE),
                    ("BatteryLifePercent", wintypes.BYTE),
                    ("SystemStatusFlag", wintypes.BYTE),
                    ("BatteryLifeTime", wintypes.DWORD),
                    ("BatteryFullLifeTime", wintypes.DWORD),
                ]

            sps = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                pct = int(sps.BatteryLifePercent) if sps.BatteryLifePercent <= 100 else None
                ac = (sps.ACLineStatus == 1) if sps.ACLineStatus in (0, 1) else None
                return PowerStatus(battery_percent=pct, power_plugged=ac, power_plan="Balanced")
        except Exception:
            pass
        return PowerStatus()
