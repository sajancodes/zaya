"""Ghost Operator UI Automation Engine.
Created and developed by Sajan Rai for Zaya.

Provides autonomous mouse, keyboard, window, and closed-loop visual UI driving
for complex end-to-end Windows desktop workflows.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from core.tool_result import ToolResult

# Mouse event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class GhostOperatorEngine:
    """Core operating-system primitive driver for UI automation."""

    def __init__(self):
        self._is_win32 = sys.platform == "win32"

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Returns the current cursor coordinates (x, y)."""
        if not self._is_win32:
            return (0, 0)
        try:
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return (pt.x, pt.y)
        except Exception:
            return (0, 0)

    def set_cursor_pos(self, x: int, y: int) -> bool:
        """Positions cursor instantly at (x, y)."""
        if not self._is_win32:
            return False
        try:
            return bool(ctypes.windll.user32.SetCursorPos(int(x), int(y)))
        except Exception:
            return False

    def move_cursor(self, x: int, y: int, smooth: bool = False, steps: int = 8) -> bool:
        """Moves cursor to (x, y) with optional interpolation."""
        if not self._is_win32:
            return False
        if not smooth or steps <= 1:
            return self.set_cursor_pos(x, y)

        cur_x, cur_y = self.get_cursor_pos()
        for i in range(1, steps + 1):
            t = i / steps
            interp_x = int(cur_x + (x - cur_x) * t)
            interp_y = int(cur_y + (y - cur_y) * t)
            self.set_cursor_pos(interp_x, interp_y)
            time.sleep(0.005)
        return self.set_cursor_pos(x, y)

    def click(
        self,
        button: str = "left",
        double: bool = False,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> bool:
        """Performs mouse click or double-click at target coordinates or current position."""
        if not self._is_win32:
            return False

        if x is not None and y is not None:
            self.move_cursor(x, y)
            time.sleep(0.02)

        btn = button.lower().strip()
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP

        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP

        try:
            ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)

            if double and btn == "left":
                time.sleep(0.06)
                ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
                time.sleep(0.01)
                ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
            return True
        except Exception:
            return False

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, steps: int = 12) -> bool:
        """Clicks down at (from_x, from_y) and smoothly drags to (to_x, to_y)."""
        if not self._is_win32:
            return False
        try:
            self.move_cursor(from_x, from_y)
            time.sleep(0.03)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            self.move_cursor(to_x, to_y, smooth=True, steps=steps)
            time.sleep(0.02)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception:
            return False

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Scrolls the mouse wheel (positive = up, negative = down)."""
        if not self._is_win32:
            return False
        if x is not None and y is not None:
            self.move_cursor(x, y)
            time.sleep(0.01)
        try:
            # 120 units per notch
            wheel_delta = int(clicks * 120)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)
            return True
        except Exception:
            return False

    def get_active_window(self) -> Dict[str, Any]:
        """Returns details about the currently active foreground window."""
        if not self._is_win32:
            return {"title": "Unsupported Platform", "hwnd": 0, "rect": {}}
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value

            rect = RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return {
                "hwnd": hwnd,
                "title": title,
                "rect": {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": max(0, rect.right - rect.left),
                    "height": max(0, rect.bottom - rect.top),
                },
            }
        except Exception as e:
            return {"hwnd": 0, "title": "", "error": str(e), "rect": {}}

    def focus_window_by_title(self, title_query: str) -> bool:
        """Finds and activates a window matching title_query substring."""
        if not self._is_win32:
            return False

        found_hwnd = 0
        q = title_query.lower().strip()

        def enum_cb(hwnd, _lparam):
            nonlocal found_hwnd
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(512)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
                if q in buf.value.lower():
                    found_hwnd = hwnd
                    return False  # stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        try:
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if found_hwnd:
                ctypes.windll.user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(found_hwnd)
                return True
        except Exception:
            pass
        return False

    def execute_workflow(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Executes a multi-step UI automation sequence with safety bounds."""
        logs = []
        executed_count = 0

        for i, step in enumerate(steps):
            action_type = str(step.get("action") or "").lower().strip()
            logs.append(f"Step {i+1}: {action_type}")

            if action_type == "click":
                x = step.get("x")
                y = step.get("y")
                btn = step.get("button", "left")
                ok = self.click(button=btn, x=x, y=y)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": f"Click failed at {x}, {y}", "logs": logs}

            elif action_type == "double_click":
                x = step.get("x")
                y = step.get("y")
                ok = self.click(button="left", double=True, x=x, y=y)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": f"Double click failed at {x}, {y}", "logs": logs}

            elif action_type == "right_click":
                x = step.get("x")
                y = step.get("y")
                ok = self.click(button="right", x=x, y=y)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": f"Right click failed at {x}, {y}", "logs": logs}

            elif action_type == "move":
                x = int(step.get("x", 0))
                y = int(step.get("y", 0))
                smooth = bool(step.get("smooth", False))
                self.move_cursor(x, y, smooth=smooth)

            elif action_type == "drag":
                from_x = int(step.get("from_x", 0))
                from_y = int(step.get("from_y", 0))
                to_x = int(step.get("to_x", 0))
                to_y = int(step.get("to_y", 0))
                ok = self.drag(from_x, from_y, to_x, to_y)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": f"Drag failed to {to_x}, {to_y}", "logs": logs}

            elif action_type == "scroll":
                clicks = int(step.get("clicks", -3))
                x = step.get("x")
                y = step.get("y")
                self.scroll(clicks, x=x, y=y)

            elif action_type == "type":
                text = str(step.get("text") or "")
                from actions.ghost_keyboard import inject_text
                ok = inject_text(text)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": "Typing injection failed", "logs": logs}

            elif action_type == "hotkey":
                hk = str(step.get("hotkey") or "")
                from actions.ghost_keyboard import send_hotkey
                ok = send_hotkey(hk)
                if not ok:
                    return {"status": "failed", "step": i + 1, "error": f"Hotkey {hk} failed", "logs": logs}

            elif action_type == "focus_window":
                title = str(step.get("title") or "")
                ok = self.focus_window_by_title(title)
                logs.append(f"Focus window '{title}': {'success' if ok else 'not found'}")

            elif action_type == "wait":
                ms = max(0, min(10000, int(step.get("ms", 200))))
                time.sleep(ms / 1000.0)

            elif action_type == "inspect_region":
                reg = step.get("region")
                from actions.screen_peeler import extract_text_from_region
                text = extract_text_from_region(reg)
                logs.append(f"Read region text: {text[:80]}...")

            else:
                return {"status": "failed", "step": i + 1, "error": f"Unknown action '{action_type}'", "logs": logs}

            executed_count += 1
            # Brief pause between sequential steps
            time.sleep(0.04)

        return {
            "status": "success",
            "steps_executed": executed_count,
            "logs": logs,
        }


# Global singleton
_operator: Optional[GhostOperatorEngine] = None


def get_ghost_operator() -> GhostOperatorEngine:
    global _operator
    if _operator is None:
        _operator = GhostOperatorEngine()
    return _operator
