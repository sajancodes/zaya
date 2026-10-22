"""Zaya Desktop Controller: Translates webcam hand tracking into global Windows input.
Webcam is the sensor (air trackpad); Monitor is the interface.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import math
import os
import sys
import time
from typing import Optional, Tuple

from core.selection.context import SelectionContext, get_selection_manager


def get_screen_size() -> Tuple[int, int]:
    """Returns primary screen width and height in pixels."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return max(800, user32.GetSystemMetrics(0)), max(600, user32.GetSystemMetrics(1))
        except Exception:
            pass
    return 1920, 1080


def get_foreground_info() -> dict:
    """Returns active window title, application name, process ID, and whether it belongs to Zaya."""
    if sys.platform != "win32":
        return {"app": "Desktop", "title": "External", "pid": 0, "is_zaya": False}
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"app": "Windows Desktop", "title": "Desktop", "pid": 0, "is_zaya": False}
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip() or "Active Window"
        app_name = "Application"
        try:
            import psutil
            proc = psutil.Process(pid.value)
            raw = proc.name().lower()
            aliases = {
                "code.exe": "Visual Studio Code",
                "brave.exe": "Brave Browser",
                "chrome.exe": "Google Chrome",
                "msedge.exe": "Microsoft Edge",
                "notepad.exe": "Notepad",
                "discord.exe": "Discord",
                "explorer.exe": "File Explorer",
                "windowsterminal.exe": "Windows Terminal",
                "cmd.exe": "Command Prompt",
                "powershell.exe": "PowerShell",
                "winword.exe": "Microsoft Word",
                "excel.exe": "Microsoft Excel"
            }
            app_name = aliases.get(raw, proc.name().replace(".exe", "").capitalize())
        except Exception:
            pass
        return {"app": app_name, "title": title, "pid": pid.value, "is_zaya": (pid.value == os.getpid())}
    except Exception:
        return {"app": "Desktop", "title": "Desktop", "pid": 0, "is_zaya": False}


class DesktopController:
    """Coordinates global mouse cursor movement, left clicks, text selection, and scrolling."""

    def __init__(self, screen_size: Optional[Tuple[int, int]] = None):
        self.screen_w, self.screen_h = screen_size or get_screen_size()

        # Pointer smoothing & filtering
        self.curr_x = float(self.screen_w // 2)
        self.curr_y = float(self.screen_h // 2)
        self.prev_x = self.curr_x
        self.prev_y = self.curr_y
        self.active_box = (0.12, 0.12, 0.88, 0.88)  # normalized (min_x, min_y, max_x, max_y)
        self.dead_zone_px = 2.0

        # State flags
        self.is_selecting = False
        self.selection_start = (0, 0)
        self.is_dragging = False

        # Click debouncing & re-arming
        self.last_click_time = 0.0
        self.click_cooldown = 0.35  # seconds
        self.click_armed = True

        # Scrolling
        self.is_scrolling = False
        self.scroll_baseline_y: Optional[float] = None
        self.last_scroll_time = 0.0
        self.scroll_interval = 0.04  # 25 updates per second max
        self.scroll_dead_zone = 0.035
        self.scroll_multiplier = 420.0

        # Thumbs up / Enter
        self.last_enter_time = 0.0
        self.enter_cooldown = 0.4

        # Target app tracking
        self.target_info = get_foreground_info()
        self._last_target_check = 0.0

    def refresh_screen_size(self):
        self.screen_w, self.screen_h = get_screen_size()

    def update_target_info(self, force: bool = False):
        now = time.monotonic()
        if force or (now - self._last_target_check > 0.5):
            self.target_info = get_foreground_info()
            self._last_target_check = now

    def map_coords(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Maps normalized trackpad coordinates to screen pixels with bounding zone clamping."""
        min_x, min_y, max_x, max_y = self.active_box
        clamped_x = max(min_x, min(max_x, norm_x))
        clamped_y = max(min_y, min(max_y, norm_y))

        rel_x = (clamped_x - min_x) / max(0.01, max_x - min_x)
        rel_y = (clamped_y - min_y) / max(0.01, max_y - min_y)

        target_px_x = rel_x * (self.screen_w - 1)
        target_px_y = rel_y * (self.screen_h - 1)
        return int(target_px_x), int(target_px_y)

    def smooth_pointer(self, target_px_x: int, target_px_y: int) -> Tuple[int, int]:
        """Smooths pointer movement using velocity-adaptive EMA and dead-zone filtering."""
        dx = target_px_x - self.curr_x
        dy = target_px_y - self.curr_y
        dist = math.hypot(dx, dy)

        if dist < self.dead_zone_px:
            return int(self.curr_x), int(self.curr_y)

        # Dynamic alpha: high speed = responsive (0.75), slow hover = steady (0.25)
        alpha = min(0.75, max(0.25, dist / 120.0))

        self.curr_x += alpha * dx
        self.curr_y += alpha * dy

        # Clamp strictly within monitor bounds
        self.curr_x = max(0.0, min(float(self.screen_w - 1), self.curr_x))
        self.curr_y = max(0.0, min(float(self.screen_h - 1), self.curr_y))

        return int(self.curr_x), int(self.curr_y)

    def _set_cursor_pos(self, x: int, y: int):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(x, y)
            except Exception:
                pass

    def _mouse_down(self):
        if sys.platform == "win32":
            try:
                import ctypes
                # MOUSEEVENTF_LEFTDOWN = 0x0002
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            except Exception:
                pass

    def _mouse_up(self):
        if sys.platform == "win32":
            try:
                import ctypes
                # MOUSEEVENTF_LEFTUP = 0x0004
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                pass

    def _mouse_click(self):
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                # MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                time.sleep(0.01)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                pass

    def _mouse_wheel(self, delta: int):
        if sys.platform == "win32":
            try:
                import ctypes
                # MOUSEEVENTF_WHEEL = 0x0800
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(delta), 0)
            except Exception:
                pass

    def handle_frame(self, hand, gesture: str, now: float) -> Tuple[int, int]:
        """Main dispatch for outside-keyboard desktop interaction."""
        self.update_target_info()

        if hand is None:
            self.on_tracking_lost()
            return int(self.curr_x), int(self.curr_y)

        # Coordinate mapping from index tip (or palm center if fist/pinch)
        if gesture in ("FIST", "PINCH", "GRAB"):
            raw_x, raw_y = hand.palm_center.x, hand.palm_center.y
        else:
            raw_x, raw_y = hand.landmarks[8].x, hand.landmarks[8].y

        target_x, target_y = self.map_coords(raw_x, raw_y)
        smooth_x, smooth_y = self.smooth_pointer(target_x, target_y)

        # 1. GESTURE: OPEN_PALM -> Smooth mouse move
        if gesture == "OPEN_PALM":
            if self.is_selecting:
                self._end_selection(smooth_x, smooth_y)
            if self.is_dragging:
                self._end_drag()
            self._end_scroll()
            self.click_armed = True
            self._set_cursor_pos(smooth_x, smooth_y)

        # 2. GESTURE: INDEX_ONLY -> Clean single click
        elif gesture == "INDEX_ONLY":
            if self.is_selecting:
                self._end_selection(smooth_x, smooth_y)
            if self.is_dragging:
                self._end_drag()
            self._end_scroll()

            self._set_cursor_pos(smooth_x, smooth_y)
            if self.click_armed and (now - self.last_click_time > self.click_cooldown):
                self._mouse_click()
                self.last_click_time = now
                self.click_armed = False

        # 3. GESTURE: TWO_FINGER -> Text / object selection drag
        elif gesture == "TWO_FINGER":
            self.click_armed = True
            self._end_scroll()
            if not self.is_selecting:
                self.is_selecting = True
                self.selection_start = (smooth_x, smooth_y)
                self._set_cursor_pos(smooth_x, smooth_y)
                self._mouse_down()
            else:
                self._set_cursor_pos(smooth_x, smooth_y)

        # 4. GESTURE: FIST -> Smooth scrolling
        elif gesture in ("FIST", "GRAB"):
            if self.is_selecting:
                self._end_selection(smooth_x, smooth_y)
            if self.is_dragging:
                self._end_drag()
            self.click_armed = True

            curr_y_val = hand.palm_center.y
            if not self.is_scrolling or self.scroll_baseline_y is None:
                self.is_scrolling = True
                self.scroll_baseline_y = curr_y_val
                self.last_scroll_time = now
            else:
                dy = curr_y_val - self.scroll_baseline_y
                if abs(dy) > self.scroll_dead_zone and (now - self.last_scroll_time >= self.scroll_interval):
                    # In image coordinates, moving hand down (+dy) scrolls DOWN (-wheel)
                    wheel_units = -int(dy * self.scroll_multiplier)
                    self._mouse_wheel(wheel_units)
                    self.last_scroll_time = now

        # 5. GESTURE: THUMBS_UP -> Enter / Submit
        elif gesture == "THUMBS_UP":
            if self.is_selecting:
                self._end_selection(smooth_x, smooth_y)
            if self.is_dragging:
                self._end_drag()
            self._end_scroll()
            self.click_armed = True

            if now - self.last_enter_time > self.enter_cooldown:
                from actions.ghost_keyboard import send_hotkey
                send_hotkey("enter")
                self.last_enter_time = now

        # 6. GESTURE: PINCH -> Hold / drag
        elif gesture == "PINCH":
            self.click_armed = True
            self._end_scroll()
            if not self.is_dragging:
                self.is_dragging = True
                self._mouse_down()
            self._set_cursor_pos(smooth_x, smooth_y)

        # Other / partial gestures
        else:
            if self.is_selecting:
                self._end_selection(smooth_x, smooth_y)
            if self.is_dragging:
                self._end_drag()
            self._end_scroll()
            self._set_cursor_pos(smooth_x, smooth_y)

        return smooth_x, smooth_y

    def _end_selection(self, end_x: int, end_y: int):
        """Releases mouse button and saves the selection context."""
        if not self.is_selecting:
            return
        self._mouse_up()
        self.is_selecting = False

        start_x, start_y = self.selection_start
        min_x = min(start_x, end_x)
        min_y = min(start_y, end_y)
        max_x = max(start_x, end_x)
        max_y = max(start_y, end_y)

        # Store context if there was meaningful drag distance
        if (max_x - min_x > 5) or (max_y - min_y > 5):
            ctx = SelectionContext(
                start=(start_x, start_y),
                end=(end_x, end_y),
                rect=(min_x, min_y, max_x, max_y),
                timestamp=time.time(),
                target_app=self.target_info.get("app", "Desktop"),
                target_title=self.target_info.get("title", ""),
                target_pid=self.target_info.get("pid", 0),
            )
            get_selection_manager().set_selection(ctx)

    def _end_drag(self):
        if not self.is_dragging:
            return
        self._mouse_up()
        self.is_dragging = False

    def _end_scroll(self):
        self.is_scrolling = False
        self.scroll_baseline_y = None

    def on_tracking_lost(self):
        """CRITICAL SAFETY: Releases any held mouse buttons and halts scrolling on tracking loss."""
        if self.is_selecting:
            self._end_selection(int(self.curr_x), int(self.curr_y))
        if self.is_dragging:
            self._end_drag()
        self._end_scroll()
        self.click_armed = True
